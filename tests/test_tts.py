from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from backend.models.tts import TTSJob, TTSJobStatus
from backend.models.user import User


class TestTTSEndpoints:
    async def test_tts_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/media/tts",
            json={"text": "Test anons metni"},
        )
        assert resp.status_code == 401

    async def test_tts_success_returns_202(
        self, client: AsyncClient, test_user: User
    ):
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login.json()["access_token"]

        with patch(
            "backend.services.tts_service.process_tts_job",
            new=AsyncMock(),
        ):
            resp = await client.post(
                "/api/v1/media/tts",
                json={
                    "text": "Sayın müşterilerimiz, mağazamız kapanış saatine yaklaşmaktadır.",
                    "language": "tr",
                    "voice_profile": "default",
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 202
        body = resp.json()
        assert "id" in body
        assert body["status"] == "pending"
        assert body["voice_profile"] == "default"
        assert body["media_id"] is None

    async def test_tts_empty_text_returns_422(
        self, client: AsyncClient, test_user: User
    ):
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login.json()["access_token"]

        resp = await client.post(
            "/api/v1/media/tts",
            json={"text": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    async def test_tts_text_too_long_returns_422(
        self, client: AsyncClient, test_user: User
    ):
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login.json()["access_token"]

        resp = await client.post(
            "/api/v1/media/tts",
            json={"text": "A" * 1001},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    async def test_tts_job_status_query(
        self, client: AsyncClient, test_user: User
    ):
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create a job first
        with patch(
            "backend.services.tts_service.process_tts_job",
            new=AsyncMock(),
        ):
            create_resp = await client.post(
                "/api/v1/media/tts",
                json={"text": "Durum sorgulama testi"},
                headers=headers,
            )

        job_id = create_resp.json()["id"]

        # Query status
        resp = await client.get(
            f"/api/v1/media/tts/{job_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == job_id
        assert body["status"] == "pending"
        assert body["text_input"] == "Durum sorgulama testi"

    async def test_tts_job_not_found_returns_404(
        self, client: AsyncClient, test_user: User
    ):
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login.json()["access_token"]

        resp = await client.get(
            "/api/v1/media/tts/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_tts_get_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/media/tts/1")
        assert resp.status_code == 401
