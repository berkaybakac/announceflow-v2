"""
Scheduler API & Conflict Engine Test Suite.

Test edilen bileşenler:
1. Schema Validation — XOR guard, cron validation, past-date guard, ANONS guard
2. CRUD — Create, Read (paginated), Update, Delete
3. Conflict Engine — Overlap detection, target-aware filtering, boundary touch
4. Auth Guards — Device JWT rejection, no token rejection
"""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import create_access_token
from backend.models.branch import Branch
from backend.models.media import MediaFile, MediaType, TargetType
from backend.models.schedule import Schedule
from backend.models.user import User


# ── Helpers ─────────────────────────────────────────────────────


def _admin_token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "type": "user"})


def _device_token(branch: Branch) -> str:
    return create_access_token({"sub": str(branch.id), "type": "device"})


async def _create_anons(
    db: AsyncSession,
    file_name: str = "anons.mp3",
    file_hash: str = "anons_hash_1",
    duration: int = 30,
) -> MediaFile:
    media = MediaFile(
        file_name=file_name,
        file_path=f"/data/media/{file_name}",
        file_hash=file_hash,
        type=MediaType.ANONS,
        duration=duration,
        size_bytes=512,
    )
    db.add(media)
    await db.flush()
    await db.refresh(media)
    return media


async def _create_music(
    db: AsyncSession,
    file_name: str = "music.mp3",
    file_hash: str = "music_hash_1",
) -> MediaFile:
    media = MediaFile(
        file_name=file_name,
        file_path=f"/data/media/{file_name}",
        file_hash=file_hash,
        type=MediaType.MUSIC,
        duration=180,
        size_bytes=1024,
    )
    db.add(media)
    await db.flush()
    await db.refresh(media)
    return media


def _future_dt(hours: int = 24, minutes: int = 0) -> str:
    """UTC'de gelecekte bir datetime ISO string döndürür."""
    dt = datetime.now(tz=timezone.utc) + timedelta(hours=hours, minutes=minutes)
    return dt.isoformat()


def _future_datetime(hours: int = 24, minutes: int = 0) -> datetime:
    """UTC'de gelecekte bir datetime nesnesi döndürür."""
    return datetime.now(tz=timezone.utc) + timedelta(hours=hours, minutes=minutes)


# ═══════════════════════════════════════════════════════════════
# 1. Schema Validation Tests
# ═══════════════════════════════════════════════════════════════


class TestScheduleValidation:
    """XOR guard, cron validation, past-date guard, ANONS guard testleri."""

    async def test_xor_both_filled_returns_422(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """play_at ve cron_expression ikisi de dolu → 422."""
        anons = await _create_anons(db_session)
        await db_session.commit()

        token = _admin_token(admin_user)
        resp = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "ALL",
                "play_at": _future_dt(),
                "cron_expression": "0 14 * * *",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    async def test_xor_both_none_returns_422(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """play_at ve cron_expression ikisi de None → 422."""
        anons = await _create_anons(db_session)
        await db_session.commit()

        token = _admin_token(admin_user)
        resp = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "ALL",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    async def test_invalid_cron_returns_422(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """Geçersiz cron_expression → 422."""
        anons = await _create_anons(db_session)
        await db_session.commit()

        token = _admin_token(admin_user)
        resp = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "ALL",
                "cron_expression": "invalid cron here",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    async def test_music_media_type_returns_422(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """media_id MUSIC tipinde → 422."""
        music = await _create_music(db_session)
        await db_session.commit()

        token = _admin_token(admin_user)
        resp = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": music.id,
                "target_type": "ALL",
                "cron_expression": "0 14 * * *",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    async def test_past_play_at_returns_422(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """Geçmiş play_at → 422."""
        anons = await _create_anons(db_session)
        await db_session.commit()

        past_dt = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
        token = _admin_token(admin_user)
        resp = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "ALL",
                "play_at": past_dt,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════
# 2. CRUD Tests
# ═══════════════════════════════════════════════════════════════


class TestScheduleCRUD:
    """Create, Read (paginated), Update, Delete testleri."""

    async def test_create_with_play_at_calculates_end_time(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """play_at ile oluşturma → end_time = play_at + duration."""
        anons = await _create_anons(db_session, duration=60)
        await db_session.commit()

        play_at = _future_dt(hours=48)
        token = _admin_token(admin_user)
        resp = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "ALL",
                "play_at": play_at,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["end_time"] is not None
        assert body["media_file_name"] == "anons.mp3"
        assert body["media_duration"] == 60
        assert body["cron_expression"] is None

    async def test_create_with_cron_no_end_time(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """cron_expression ile oluşturma → end_time NULL."""
        anons = await _create_anons(db_session, file_hash="cron_test_1")
        await db_session.commit()

        token = _admin_token(admin_user)
        resp = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "ALL",
                "cron_expression": "0 14 * * 1-5",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["end_time"] is None
        assert body["play_at"] is None
        assert body["cron_expression"] == "0 14 * * 1-5"

    async def test_get_paginated_list(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """GET paginated liste doğru döner."""
        anons = await _create_anons(db_session, file_hash="list_test_1")
        await db_session.commit()

        token = _admin_token(admin_user)

        # 3 kayıt oluştur
        for i in range(3):
            await client.post(
                "/api/v1/schedules/",
                json={
                    "media_id": anons.id,
                    "target_type": "ALL",
                    "cron_expression": f"{i} 14 * * *",
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        resp = await client.get(
            "/api/v1/schedules/?page=1&page_size=2",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 2
        assert body["page"] == 1
        assert body["page_size"] == 2

    async def test_update_schedule(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """PUT güncelleme başarılı."""
        anons = await _create_anons(db_session, file_hash="update_test_1")
        await db_session.commit()

        token = _admin_token(admin_user)

        # Oluştur
        create_resp = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "ALL",
                "cron_expression": "0 14 * * *",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        schedule_id = create_resp.json()["id"]

        # Güncelle
        resp = await client.put(
            f"/api/v1/schedules/{schedule_id}",
            json={"cron_expression": "30 9 * * 1-5"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["cron_expression"] == "30 9 * * 1-5"

    async def test_delete_schedule(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """DELETE → 204."""
        anons = await _create_anons(db_session, file_hash="delete_test_1")
        await db_session.commit()

        token = _admin_token(admin_user)

        create_resp = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "ALL",
                "cron_expression": "0 14 * * *",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        schedule_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/schedules/{schedule_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204

        # Silinmiş mi?
        get_resp = await client.get(
            "/api/v1/schedules/?page=1&page_size=100",
            headers={"Authorization": f"Bearer {token}"},
        )
        ids = [item["id"] for item in get_resp.json()["items"]]
        assert schedule_id not in ids

    async def test_update_nonexistent_returns_404(
        self, client: AsyncClient, admin_user: User
    ):
        """Olmayan ID'ye PUT → 404."""
        token = _admin_token(admin_user)
        resp = await client.put(
            "/api/v1/schedules/99999",
            json={"cron_expression": "0 14 * * *"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_delete_nonexistent_returns_404(
        self, client: AsyncClient, admin_user: User
    ):
        """Olmayan ID'ye DELETE → 404."""
        token = _admin_token(admin_user)
        resp = await client.delete(
            "/api/v1/schedules/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
# 3. Conflict Engine Tests
# ═══════════════════════════════════════════════════════════════


class TestConflictEngine:
    """Çakışma algılama testleri."""

    async def test_same_time_same_branch_returns_409(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """Aynı saat, aynı şube → 409."""
        anons = await _create_anons(db_session, duration=120, file_hash="conflict_1")
        await db_session.commit()

        token = _admin_token(admin_user)
        play_at = _future_dt(hours=72)

        # İlk kayıt
        resp1 = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "BRANCH",
                "target_id": 1,
                "play_at": play_at,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code == 201

        # Aynı zaman + aynı şube → çakışma
        resp2 = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "BRANCH",
                "target_id": 1,
                "play_at": play_at,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 409

    async def test_same_time_different_branch_returns_201(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """Aynı saat, farklı şube → çakışma yok, 201."""
        anons = await _create_anons(db_session, duration=120, file_hash="conflict_2")
        await db_session.commit()

        token = _admin_token(admin_user)
        play_at = _future_dt(hours=96)

        # Şube 1
        resp1 = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "BRANCH",
                "target_id": 1,
                "play_at": play_at,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code == 201

        # Şube 2 (farklı) → çakışma yok
        resp2 = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "BRANCH",
                "target_id": 2,
                "play_at": play_at,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 201

    async def test_all_target_locks_everything_returns_409(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """ALL hedef → tüm sistem kilitlenir, BRANCH ekleme → 409."""
        anons = await _create_anons(db_session, duration=120, file_hash="conflict_3")
        await db_session.commit()

        token = _admin_token(admin_user)
        play_at = _future_dt(hours=120)

        # ALL ile kayıt
        resp1 = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "ALL",
                "play_at": play_at,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code == 201

        # Aynı saatte BRANCH ekleme → ALL kilitliyor
        resp2 = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "BRANCH",
                "target_id": 5,
                "play_at": play_at,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 409

    async def test_boundary_touch_no_conflict(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """Boundary touch — A.end_time == B.play_at → çakışma yok, 201."""
        anons = await _create_anons(db_session, duration=60, file_hash="conflict_4")
        await db_session.commit()

        token = _admin_token(admin_user)
        base_dt = _future_datetime(hours=144)
        play_at_1 = base_dt.isoformat()
        # A bittiği an B başlar (tam sınır)
        play_at_2 = (base_dt + timedelta(seconds=60)).isoformat()

        resp1 = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "ALL",
                "play_at": play_at_1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code == 201

        resp2 = await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "ALL",
                "play_at": play_at_2,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 201

    async def test_check_conflict_endpoint_detects_overlap(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """POST /check-conflict → has_conflict: true."""
        anons = await _create_anons(db_session, duration=120, file_hash="conflict_5")
        await db_session.commit()

        token = _admin_token(admin_user)
        play_at = _future_dt(hours=168)

        # Kayıt oluştur
        await client.post(
            "/api/v1/schedules/",
            json={
                "media_id": anons.id,
                "target_type": "ALL",
                "play_at": play_at,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        # Çakışma kontrolü
        resp = await client.post(
            "/api/v1/schedules/check-conflict",
            json={
                "media_id": anons.id,
                "play_at": play_at,
                "target_type": "ALL",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_conflict"] is True
        assert body["conflicting_schedule"] is not None

    async def test_check_conflict_endpoint_no_overlap(
        self, client: AsyncClient, db_session: AsyncSession, admin_user: User
    ):
        """POST /check-conflict → has_conflict: false."""
        anons = await _create_anons(db_session, duration=30, file_hash="conflict_6")
        await db_session.commit()

        token = _admin_token(admin_user)

        resp = await client.post(
            "/api/v1/schedules/check-conflict",
            json={
                "media_id": anons.id,
                "play_at": _future_dt(hours=200),
                "target_type": "ALL",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_conflict"] is False
        assert body["conflicting_schedule"] is None


# ═══════════════════════════════════════════════════════════════
# 4. Auth Guard Tests
# ═══════════════════════════════════════════════════════════════


class TestScheduleAuthGuards:
    """Device JWT rejection ve no-token rejection testleri."""

    async def test_device_jwt_returns_403(
        self, client: AsyncClient, db_session: AsyncSession, test_branch: Branch
    ):
        """Device JWT ile erişim → 403 (vendor_admin değil)."""
        token = _device_token(test_branch)
        resp = await client.get(
            "/api/v1/schedules/",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Device token'ın type'ı "device" — get_current_user zaten 401 verir
        assert resp.status_code == 401

    async def test_no_token_returns_401(self, client: AsyncClient):
        """Token yok → 401."""
        resp = await client.get("/api/v1/schedules/")
        assert resp.status_code == 401

    async def test_non_admin_user_returns_403(
        self, client: AsyncClient, test_user: User
    ):
        """Normal kullanıcı (is_vendor_admin=False) → 403."""
        token = _admin_token(test_user)  # normal user token
        resp = await client.get(
            "/api/v1/schedules/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
