"""
Manifest API (Sync Engine) Test Suite.

Test edilen bileşenler:
1. MediaRepository.get_music_for_branch — 3'lü ACL (ALL ∪ BRANCH ∪ GROUP)
2. ScheduleRepository.get_schedules_for_branch_with_media — 3'lü ACL + JOIN
3. BranchRepository.update_last_sync — last_sync_at + sync_status güncelleme
4. ManifestService.build_manifest — Manifest JSON yapısı
5. Manifest Router — Auth guard, branch_id eşleşme, sync_confirm
"""

from datetime import time

import pytest
from httpx import AsyncClient  # noqa: TC002
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from backend.core.security import create_access_token
from backend.models.branch import Branch, BranchSettings
from backend.models.media import MediaFile, MediaTarget, MediaType, TargetType
from backend.models.schedule import Schedule
from backend.models.user import User
from backend.repositories.branch_repository import BranchRepository
from backend.repositories.media_repository import MediaRepository
from backend.repositories.schedule_repository import ScheduleRepository

# ── Helpers ─────────────────────────────────────────────────────


def _device_token(branch: Branch) -> str:
    return create_access_token({"sub": str(branch.id), "type": "device"})


def _admin_token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "type": "user"})


async def _create_music(
    db: AsyncSession,
    file_name: str = "test.mp3",
    file_hash: str = "abc123",
    size_bytes: int = 1024,
) -> MediaFile:
    media = MediaFile(
        file_name=file_name,
        file_path=f"/data/media/{file_name}",
        file_hash=file_hash,
        type=MediaType.MUSIC,
        duration=180,
        size_bytes=size_bytes,
    )
    db.add(media)
    await db.flush()
    await db.refresh(media)
    return media


async def _create_anons(
    db: AsyncSession,
    file_name: str = "anons.mp3",
    file_hash: str = "def456",
    size_bytes: int = 512,
) -> MediaFile:
    media = MediaFile(
        file_name=file_name,
        file_path=f"/data/media/{file_name}",
        file_hash=file_hash,
        type=MediaType.ANONS,
        duration=30,
        size_bytes=size_bytes,
    )
    db.add(media)
    await db.flush()
    await db.refresh(media)
    return media


async def _assign_target(
    db: AsyncSession,
    media: MediaFile,
    target_type: TargetType,
    target_id: int | None = None,
    target_group: str | None = None,
) -> MediaTarget:
    target = MediaTarget(
        media_id=media.id,
        target_type=target_type,
        target_id=target_id,
        target_group=target_group,
    )
    db.add(target)
    await db.flush()
    return target


async def _create_schedule(
    db: AsyncSession,
    media: MediaFile,
    target_type: TargetType,
    target_id: int | None = None,
    target_group: str | None = None,
    is_active: bool = True,
    cron_expression: str | None = "0 14 * * *",
) -> Schedule:
    schedule = Schedule(
        media_id=media.id,
        target_type=target_type,
        target_id=target_id,
        target_group=target_group,
        is_active=is_active,
        cron_expression=cron_expression,
    )
    db.add(schedule)
    await db.flush()
    await db.refresh(schedule)
    return schedule


async def _create_branch_with_settings(
    db: AsyncSession,
    name: str = "Test Şube",
    group_tag: str | None = None,
) -> Branch:
    branch = Branch(
        name=name,
        city="Gaziantep",
        district="Şahinbey",
        token=f"token-{name}",
        is_active=True,
        volume_music=50,
        volume_announce=80,
        group_tag=group_tag,
    )
    db.add(branch)
    await db.flush()
    await db.refresh(branch)

    settings = BranchSettings(
        branch_id=branch.id,
        work_start=time(9, 0),
        work_end=time(22, 0),
        prayer_tracking=False,
        prayer_margin=10,
        city_code=27,
        loop_mode="shuffle_loop",
    )
    db.add(settings)
    await db.flush()
    return branch


# ═══════════════════════════════════════════════════════════════
# 1. Repository — MediaRepository.get_music_for_branch
# ═══════════════════════════════════════════════════════════════


class TestMediaRepositoryACL:
    """3'lü ACL kuralı testleri (ALL ∪ BRANCH ∪ GROUP)."""

    async def test_returns_music_for_branch_target(
        self, db_session: AsyncSession, test_branch: Branch
    ):
        """BRANCH hedefli müzik manifest'te var."""
        music = await _create_music(db_session, "branch_hit.mp3", "h1")
        await _assign_target(
            db_session, music, TargetType.BRANCH, target_id=test_branch.id
        )
        await db_session.commit()

        repo = MediaRepository(db_session)
        result = await repo.get_music_for_branch(
            test_branch.id, test_branch.group_tag
        )
        assert len(result) == 1
        assert result[0].file_name == "branch_hit.mp3"

    async def test_returns_music_for_all_target(
        self, db_session: AsyncSession, test_branch: Branch
    ):
        """ALL hedefli müzik tüm branch'lere döner."""
        music = await _create_music(db_session, "global_hit.mp3", "h2")
        await _assign_target(db_session, music, TargetType.ALL)
        await db_session.commit()

        repo = MediaRepository(db_session)
        result = await repo.get_music_for_branch(
            test_branch.id, test_branch.group_tag
        )
        assert len(result) == 1
        assert result[0].file_name == "global_hit.mp3"

    async def test_returns_music_for_group_target(
        self, db_session: AsyncSession
    ):
        """GROUP hedefli müzik, eşleşen group_tag'e döner."""
        branch = await _create_branch_with_settings(
            db_session, name="İstanbul Şube", group_tag="istanbul"
        )
        music = await _create_music(db_session, "istanbul_hit.mp3", "h3")
        await _assign_target(
            db_session, music, TargetType.GROUP, target_group="istanbul"
        )
        await db_session.commit()

        repo = MediaRepository(db_session)
        result = await repo.get_music_for_branch(branch.id, branch.group_tag)
        assert len(result) == 1
        assert result[0].file_name == "istanbul_hit.mp3"

    async def test_excludes_unrelated_branch(
        self, db_session: AsyncSession, test_branch: Branch
    ):
        """Başka branch'e atanmış müzik gelmez."""
        music = await _create_music(db_session, "other.mp3", "h4")
        await _assign_target(
            db_session, music, TargetType.BRANCH, target_id=99999
        )
        await db_session.commit()

        repo = MediaRepository(db_session)
        result = await repo.get_music_for_branch(
            test_branch.id, test_branch.group_tag
        )
        assert len(result) == 0

    async def test_excludes_unrelated_group(
        self, db_session: AsyncSession, test_branch: Branch
    ):
        """Farklı group_tag müzik gelmez."""
        music = await _create_music(db_session, "ankara.mp3", "h5")
        await _assign_target(
            db_session, music, TargetType.GROUP, target_group="ankara"
        )
        await db_session.commit()

        repo = MediaRepository(db_session)
        result = await repo.get_music_for_branch(
            test_branch.id, test_branch.group_tag  # group_tag=None
        )
        assert len(result) == 0

    async def test_no_duplicate_music(self, db_session: AsyncSession):
        """Birden fazla kuraldan eşleşen müzik DISTINCT ile tek döner."""
        branch = await _create_branch_with_settings(
            db_session, name="Multi Rule", group_tag="multi"
        )
        music = await _create_music(db_session, "multi.mp3", "h6")
        # Aynı müzik hem ALL hem GROUP ile atanmış
        await _assign_target(db_session, music, TargetType.ALL)
        await _assign_target(
            db_session, music, TargetType.GROUP, target_group="multi"
        )
        await db_session.commit()

        repo = MediaRepository(db_session)
        result = await repo.get_music_for_branch(branch.id, branch.group_tag)
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════
# 2. Repository — ScheduleRepository.get_schedules_for_branch_with_media
# ═══════════════════════════════════════════════════════════════


class TestScheduleRepositoryACL:
    """Schedule ACL + media JOIN testleri."""

    async def test_returns_schedules_for_branch(
        self, db_session: AsyncSession, test_branch: Branch
    ):
        """Aktif anons schedule'ları doğru döner."""
        anons = await _create_anons(db_session, "kampanya.mp3", "a1")
        await _create_schedule(
            db_session, anons, TargetType.BRANCH, target_id=test_branch.id
        )
        await db_session.commit()

        repo = ScheduleRepository(db_session)
        rows = await repo.get_schedules_for_branch_with_media(
            test_branch.id, test_branch.group_tag
        )
        assert len(rows) == 1
        sched, media = rows[0]
        assert media.file_name == "kampanya.mp3"

    async def test_excludes_inactive_schedules(
        self, db_session: AsyncSession, test_branch: Branch
    ):
        """is_active=False schedule dahil edilmez."""
        anons = await _create_anons(db_session, "eski.mp3", "a2")
        await _create_schedule(
            db_session,
            anons,
            TargetType.BRANCH,
            target_id=test_branch.id,
            is_active=False,
        )
        await db_session.commit()

        repo = ScheduleRepository(db_session)
        rows = await repo.get_schedules_for_branch_with_media(
            test_branch.id, test_branch.group_tag
        )
        assert len(rows) == 0


# ═══════════════════════════════════════════════════════════════
# 3. Repository — BranchRepository.update_last_sync
# ═══════════════════════════════════════════════════════════════


class TestBranchRepositorySyncUpdate:
    """Sync update testleri."""

    async def test_update_last_sync(
        self, db_session: AsyncSession, test_branch: Branch
    ):
        """Sync onayı last_sync_at ve sync_status günceller."""
        assert test_branch.last_sync_at is None
        assert test_branch.sync_status is None

        repo = BranchRepository(db_session)
        result = await repo.update_last_sync(test_branch.id, sync_status="ok")
        assert result is True

        await db_session.refresh(test_branch)
        assert test_branch.last_sync_at is not None
        assert test_branch.sync_status == "ok"

    async def test_update_last_sync_nonexistent(
        self, db_session: AsyncSession
    ):
        """Olmayan branch → False."""
        repo = BranchRepository(db_session)
        result = await repo.update_last_sync(99999, sync_status="ok")
        assert result is False


# ═══════════════════════════════════════════════════════════════
# 4. Manifest Router — API Integration Tests
# ═══════════════════════════════════════════════════════════════


class TestManifestRouter:
    """GET /api/v1/manifest/{branch_id} endpoint testleri."""

    async def test_manifest_returns_music_and_settings(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Tam manifest müzik, anons ve settings ile döner."""
        branch = await _create_branch_with_settings(db_session, "API Şube")
        music = await _create_music(db_session, "api_track.mp3", "api1")
        await _assign_target(
            db_session, music, TargetType.BRANCH, target_id=branch.id
        )
        anons = await _create_anons(db_session, "api_anons.mp3", "api2")
        await _create_schedule(
            db_session, anons, TargetType.BRANCH, target_id=branch.id
        )
        await db_session.commit()

        token = _device_token(branch)
        resp = await client.get(
            f"/api/v1/manifest/{branch.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()

        # Structure
        assert body["branch_id"] == branch.id
        assert "generated_at" in body

        # Music
        assert len(body["music"]) == 1
        assert body["music"][0]["file_name"] == "api_track.mp3"
        assert body["music"][0]["file_hash"] == "api1"
        assert body["music"][0]["download_url"] == f"/api/v1/media/download/{music.id}"

        # Announcements
        assert len(body["announcements"]) == 1
        assert body["announcements"][0]["media_file_name"] == "api_anons.mp3"

        # Settings — strftime type safety
        assert body["settings"]["work_start"] == "09:00"
        assert body["settings"]["work_end"] == "22:00"
        assert body["settings"]["volume_music"] == 50
        assert body["settings"]["loop_mode"] == "shuffle_loop"

    async def test_manifest_auth_device_only(
        self, client: AsyncClient, admin_user: User
    ):
        """Admin JWT ile manifest erişimi → 401."""
        token = _admin_token(admin_user)
        resp = await client.get(
            "/api/v1/manifest/1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    async def test_manifest_auth_no_token(self, client: AsyncClient):
        """Token yok → 401."""
        resp = await client.get("/api/v1/manifest/1")
        assert resp.status_code == 401

    async def test_manifest_branch_id_mismatch(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """URL branch_id ≠ token branch_id → 403."""
        branch = await _create_branch_with_settings(db_session, "Mismatch Şube")
        await db_session.commit()

        token = _device_token(branch)
        wrong_id = branch.id + 999
        resp = await client.get(
            f"/api/v1/manifest/{wrong_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_manifest_no_settings_returns_null(
        self, client: AsyncClient, test_branch: Branch
    ):
        """Settings yoksa settings alanı null döner."""
        token = _device_token(test_branch)
        resp = await client.get(
            f"/api/v1/manifest/{test_branch.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["settings"] is None


# ═══════════════════════════════════════════════════════════════
# 5. Sync Confirm Router — POST /api/v1/agent/sync_confirm
# ═══════════════════════════════════════════════════════════════


class TestSyncConfirmRouter:
    """POST /api/v1/agent/sync_confirm endpoint testleri."""

    async def test_sync_confirm_updates_last_sync(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """POST sonrası last_sync_at güncellenir."""
        branch = await _create_branch_with_settings(db_session, "Sync Şube")
        await db_session.commit()

        token = _device_token(branch)
        resp = await client.post(
            "/api/v1/agent/sync_confirm",
            json={"synced_files_count": 5, "status": "ok"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True

        await db_session.refresh(branch)
        assert branch.last_sync_at is not None
        assert branch.sync_status == "ok"

    async def test_sync_confirm_partial_status(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Partial sync durumu DB'ye doğru status ile yazılır."""
        branch = await _create_branch_with_settings(db_session, "Partial Şube")
        await db_session.commit()

        token = _device_token(branch)
        resp = await client.post(
            "/api/v1/agent/sync_confirm",
            json={"synced_files_count": 3, "status": "partial"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert "partial" in body["message"]

        await db_session.refresh(branch)
        assert branch.sync_status == "partial"

    async def test_sync_confirm_auth_device_only(
        self, client: AsyncClient, admin_user: User
    ):
        """Admin JWT ile sync_confirm erişimi → 401."""
        token = _admin_token(admin_user)
        resp = await client.post(
            "/api/v1/agent/sync_confirm",
            json={"synced_files_count": 5, "status": "ok"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
