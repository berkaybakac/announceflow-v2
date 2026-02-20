from datetime import timedelta

import pytest
from httpx import AsyncClient  # noqa: TC002

from backend.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from backend.models.branch import Branch
from backend.models.user import User

# ── Security utils ──────────────────────────────────────────────


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("mypassword")
        assert hashed != "mypassword"
        assert verify_password("mypassword", hashed) is True

    def test_wrong_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False


class TestJWT:
    def test_create_and_decode(self):
        data = {"sub": "1", "type": "user", "is_vendor_admin": False}
        token = create_access_token(data)
        payload = decode_access_token(token)
        assert payload["sub"] == "1"
        assert payload["type"] == "user"
        assert "exp" in payload

    def test_expired_token(self):
        import jwt

        data = {"sub": "1", "type": "user"}
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(token)


# ── Login endpoint ──────────────────────────────────────────────


class TestLogin:
    async def test_login_success(self, client: AsyncClient, test_user: User):
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

        payload = decode_access_token(body["access_token"])
        assert payload["sub"] == str(test_user.id)
        assert payload["type"] == "user"

    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "wrongpass"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "ghost", "password": "whatever"},
        )
        assert resp.status_code == 401


# ── Handshake endpoint ─────────────────────────────────────────


class TestHandshake:
    async def test_handshake_success(self, client: AsyncClient, test_branch: Branch):
        resp = await client.post(
            "/api/v1/agent/handshake",
            json={"device_token": "test-device-token-uuid"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["branch_id"] == test_branch.id
        assert body["token_type"] == "bearer"

        payload = decode_access_token(body["access_token"])
        assert payload["type"] == "device"
        assert payload["sub"] == str(test_branch.id)

    async def test_handshake_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/agent/handshake",
            json={"device_token": "nonexistent-token"},
        )
        assert resp.status_code == 401

    async def test_handshake_inactive_device(
        self, client: AsyncClient, inactive_branch: Branch
    ):
        resp = await client.post(
            "/api/v1/agent/handshake",
            json={"device_token": "inactive-device-token-uuid"},
        )
        assert resp.status_code == 403
        assert "devre dışı" in resp.json()["detail"]


# ── Vendor admin guard ──────────────────────────────────────────


class TestVendorAdminGuard:
    async def test_admin_access(self, client: AsyncClient, admin_user: User):
        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "adminpass123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_vendor_admin"] is True

    async def test_regular_user_access(self, client: AsyncClient, test_user: User):
        login_resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_vendor_admin"] is False
