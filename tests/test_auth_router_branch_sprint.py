from datetime import timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.user import User
from backend.routers import auth as auth_router
from backend.schemas.auth import HandshakeRequest


async def test_login_invalid_credentials_returns_401() -> None:
    form = OAuth2PasswordRequestForm(username="ghost", password="wrong", scope="")
    repo = MagicMock()
    repo.get_by_username = AsyncMock(return_value=None)
    db = cast(AsyncSession, MagicMock())

    with patch.object(auth_router, "UserRepository", return_value=repo):
        with pytest.raises(HTTPException) as exc:
            await auth_router.login(form_data=form, db=db)

    assert exc.value.status_code == 401
    assert "Geçersiz kullanıcı adı veya şifre" in str(exc.value.detail)


async def test_login_inactive_user_returns_401() -> None:
    form = OAuth2PasswordRequestForm(username="inactive", password="secret", scope="")
    inactive_user = SimpleNamespace(
        id=7,
        password_hash="hash",
        is_active=False,
        is_vendor_admin=False,
    )
    repo = MagicMock()
    repo.get_by_username = AsyncMock(return_value=inactive_user)
    db = cast(AsyncSession, MagicMock())

    with (
        patch.object(auth_router, "UserRepository", return_value=repo),
        patch.object(auth_router, "verify_password", return_value=True),
    ):
        with pytest.raises(HTTPException) as exc:
            await auth_router.login(form_data=form, db=db)

    assert exc.value.status_code == 401
    assert "Hesap devre dışı" in str(exc.value.detail)


async def test_login_success_returns_token_response() -> None:
    form = OAuth2PasswordRequestForm(username="active", password="secret", scope="")
    user = SimpleNamespace(
        id=9,
        password_hash="hash",
        is_active=True,
        is_vendor_admin=True,
    )
    repo = MagicMock()
    repo.get_by_username = AsyncMock(return_value=user)
    db = cast(AsyncSession, MagicMock())

    with (
        patch.object(auth_router, "UserRepository", return_value=repo),
        patch.object(auth_router, "verify_password", return_value=True),
        patch.object(auth_router, "create_access_token", return_value="jwt-user") as token_mock,
    ):
        resp = await auth_router.login(form_data=form, db=db)

    assert resp.access_token == "jwt-user"
    assert resp.token_type == "bearer"
    token_mock.assert_called_once_with(
        data={"sub": "9", "type": "user", "is_vendor_admin": True}
    )


async def test_agent_handshake_invalid_token_returns_401() -> None:
    repo = MagicMock()
    repo.get_by_token = AsyncMock(return_value=None)
    db = cast(AsyncSession, MagicMock())

    with patch.object(auth_router, "BranchRepository", return_value=repo):
        with pytest.raises(HTTPException) as exc:
            await auth_router.agent_handshake(
                body=HandshakeRequest(device_token="invalid"),
                db=db,
            )

    assert exc.value.status_code == 401
    assert "Geçersiz cihaz token" in str(exc.value.detail)


async def test_agent_handshake_inactive_branch_returns_403() -> None:
    repo = MagicMock()
    repo.get_by_token = AsyncMock(return_value=SimpleNamespace(id=5, is_active=False))
    db = cast(AsyncSession, MagicMock())

    with patch.object(auth_router, "BranchRepository", return_value=repo):
        with pytest.raises(HTTPException) as exc:
            await auth_router.agent_handshake(
                body=HandshakeRequest(device_token="inactive"),
                db=db,
            )

    assert exc.value.status_code == 403
    assert "Cihaz devre dışı" in str(exc.value.detail)


async def test_agent_handshake_success_returns_device_token() -> None:
    branch = SimpleNamespace(id=11, is_active=True)
    repo = MagicMock()
    repo.get_by_token = AsyncMock(return_value=branch)
    db = cast(AsyncSession, MagicMock())

    with (
        patch.object(auth_router, "BranchRepository", return_value=repo),
        patch.object(
            auth_router,
            "create_access_token",
            return_value="jwt-device",
        ) as token_mock,
    ):
        resp = await auth_router.agent_handshake(
            body=HandshakeRequest(device_token="valid-device"),
            db=db,
        )

    assert resp.access_token == "jwt-device"
    assert resp.branch_id == 11
    assert resp.token_type == "bearer"
    assert token_mock.call_args.kwargs["data"] == {"sub": "11", "type": "device"}
    assert token_mock.call_args.kwargs["expires_delta"] == timedelta(
        days=auth_router.settings.DEVICE_TOKEN_EXPIRE_DAYS
    )


async def test_me_maps_current_user_to_user_read() -> None:
    current_user = SimpleNamespace(
        id=42,
        username="ops-admin",
        is_vendor_admin=True,
        is_active=True,
    )

    resp = await auth_router.me(current_user=cast(User, current_user))

    assert resp.id == 42
    assert resp.username == "ops-admin"
    assert resp.is_vendor_admin is True
    assert resp.is_active is True
