from pathlib import Path
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import create_access_token
from backend.models.branch import Branch
from backend.models.media import MediaFile, MediaType
from backend.models.user import User


def _device_token(branch: Branch) -> str:
    return create_access_token({"sub": str(branch.id), "type": "device"})


def _user_token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "type": "user"})


class TestMediaUpload:
    async def test_upload_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/media/upload",
            files={"file": ("test.mp3", b"fake", "audio/mpeg")},
            data={"media_type": "MUSIC"},
        )
        assert resp.status_code == 401

    async def test_upload_success_returns_202(
        self, client: AsyncClient, test_user: User
    ):
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login.json()["access_token"]

        with (
            patch(
                "backend.services.media_service.save_upload_to_temp",
                new=AsyncMock(return_value=Path("fake/path/song.mp3")),
            ),
            patch(
                "backend.services.media_service.probe_audio",
                new=AsyncMock(
                    return_value={"has_audio": True, "duration_seconds": 120}
                ),
            ),
            patch(
                "backend.services.media_service.compute_sha256",
                return_value="a" * 64,
            ),
            patch(
                "backend.services.media_service.normalize_audio",
                new=AsyncMock(),
            ),
        ):
            resp = await client.post(
                "/api/v1/media/upload",
                files={"file": ("song.mp3", b"fake_mp3_bytes", "audio/mpeg")},
                data={"media_type": "MUSIC"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 202
        body = resp.json()
        assert "media_id" in body
        assert body["status"] == "processing"
        assert body["file_name"] == "song.mp3"

    async def test_upload_invalid_audio_returns_422(
        self, client: AsyncClient, test_user: User
    ):
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login.json()["access_token"]

        with (
            patch(
                "backend.services.media_service.save_upload_to_temp",
                new=AsyncMock(return_value=Path("fake/path/bad.txt")),
            ),
            patch(
                "backend.services.media_service.probe_audio",
                new=AsyncMock(
                    return_value={"has_audio": False, "duration_seconds": 0}
                ),
            ),
        ):
            resp = await client.post(
                "/api/v1/media/upload",
                files={"file": ("not_audio.txt", b"text content", "text/plain")},
                data={"media_type": "MUSIC"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 422
        assert "ses" in resp.json()["detail"]

    async def test_upload_duplicate_returns_409(
        self, client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        known_hash = "b" * 64
        existing = MediaFile(
            file_name="existing.mp3",
            file_path="/data/media/1.mp3",
            file_hash=known_hash,
            type=MediaType.MUSIC,
            duration=60,
            size_bytes=1024,
        )
        db_session.add(existing)
        await db_session.commit()

        login = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login.json()["access_token"]

        with (
            patch(
                "backend.services.media_service.save_upload_to_temp",
                new=AsyncMock(return_value=Path("fake/path/dup.mp3")),
            ),
            patch(
                "backend.services.media_service.probe_audio",
                new=AsyncMock(
                    return_value={"has_audio": True, "duration_seconds": 60}
                ),
            ),
            patch(
                "backend.services.media_service.compute_sha256",
                return_value=known_hash,
            ),
        ):
            resp = await client.post(
                "/api/v1/media/upload",
                files={"file": ("dup.mp3", b"fake", "audio/mpeg")},
                data={"media_type": "MUSIC"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 409

    async def test_upload_invalid_media_type_returns_422(
        self, client: AsyncClient, test_user: User
    ):
        login = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpass123"},
        )
        token = login.json()["access_token"]

        resp = await client.post(
            "/api/v1/media/upload",
            files={"file": ("song.mp3", b"fake", "audio/mpeg")},
            data={"media_type": "INVALID_TYPE"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422


class TestMediaDownload:
    async def test_download_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/media/1/download")
        assert resp.status_code == 401

    async def test_download_rejects_user_token(
        self, client: AsyncClient, test_user: User
    ):
        token = _user_token(test_user)
        resp = await client.get(
            "/api/v1/media/1/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    async def test_download_returns_mp3_file(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_branch: Branch,
        tmp_path: Path,
    ):
        file_bytes = b"ID3\x04\x00\x00\x00\x00\x00\x00fake-mp3-bytes"
        file_path = tmp_path / "downloadable.mp3"
        file_path.write_bytes(file_bytes)

        media = MediaFile(
            file_name="downloadable.mp3",
            file_path=str(file_path),
            file_hash="c" * 64,
            type=MediaType.MUSIC,
            duration=120,
            size_bytes=len(file_bytes),
        )
        db_session.add(media)
        await db_session.commit()
        await db_session.refresh(media)

        token = _device_token(test_branch)
        resp = await client.get(
            f"/api/v1/media/{media.id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("audio/mpeg")
        assert resp.content == file_bytes

    async def test_download_returns_404_when_media_missing(
        self, client: AsyncClient, test_branch: Branch
    ):
        token = _device_token(test_branch)
        resp = await client.get(
            "/api/v1/media/999999/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_download_returns_404_when_file_missing(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_branch: Branch,
        tmp_path: Path,
    ):
        missing_path = tmp_path / "missing.mp3"
        media = MediaFile(
            file_name="missing.mp3",
            file_path=str(missing_path),
            file_hash="d" * 64,
            type=MediaType.MUSIC,
            duration=30,
            size_bytes=123,
        )
        db_session.add(media)
        await db_session.commit()
        await db_session.refresh(media)

        token = _device_token(test_branch)
        resp = await client.get(
            f"/api/v1/media/{media.id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
