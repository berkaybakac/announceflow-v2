"""
Heartbeat Monitor Test Suite.

Test edilen bileşenler:
1. TelemetryCache — In-memory cache CRUD ve stale detection
2. HeartbeatService — Topic parsing, status/LWT handlers, reaper
3. BranchRepository — set_online_status, set_bulk_offline
4. Telemetry Router — Admin-only GET endpoints
"""

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient  # noqa: TC002
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from backend.core.security import create_access_token
from backend.models.branch import Branch
from backend.models.user import User
from backend.repositories.branch_repository import BranchRepository
from backend.services import heartbeat_service
from backend.services.heartbeat_service import parse_payload, parse_topic
from backend.services.telemetry_cache import TelemetryCache, telemetry_cache

# ── Helpers ─────────────────────────────────────────────────────


def _admin_token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "type": "user"})


def _user_token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "type": "user"})


def _sample_payload() -> dict:
    return {
        "status": True,
        "current_track": "summer_hit.mp3",
        "disk_usage": 45.2,
        "cpu_temp": 52.1,
        "ram_usage": 38.5,
        "last_sync": "2026-02-24T09:00:00Z",
        "loop_active": True,
    }


# ═══════════════════════════════════════════════════════════════
# 1. TelemetryCache Unit Tests
# ═══════════════════════════════════════════════════════════════


class TestTelemetryCache:
    """In-memory singleton cache testleri."""

    def setup_method(self):
        """Her test öncesi taze cache oluştur."""
        self.cache = TelemetryCache()

    def test_update_and_get(self):
        """Cache'e veri yaz, geri oku — payload doğru dönmeli."""
        payload = _sample_payload()
        self.cache.update(1, payload)

        result = self.cache.get(1)
        assert result is not None
        assert result["current_track"] == "summer_hit.mp3"
        assert result["cpu_temp"] == 52.1
        assert result["status"] is True
        assert "last_seen" in result

    def test_get_nonexistent_returns_none(self):
        """Olmayan branch_id → None."""
        assert self.cache.get(999) is None

    def test_update_sanitizes_invalid_fields(self):
        """Blueprint dışı/bozuk alanlar filtrelenir, sağlam alanlar saklanır."""
        payload = {
            "status": "true",
            "cpu_temp": "hot",
            "disk_usage": 150,
            "ram_usage": 38.5,
            "current_track": "x" * 64,
            "last_sync": "2026-02-24T09:00:00Z",
            "hacker_field": "malicious",
            "extra_data": 42,
        }
        self.cache.update(1, payload, max_string_length=32, force_status=True)
        result = self.cache.get(1)
        assert result is not None
        assert "hacker_field" not in result
        assert "extra_data" not in result
        assert "cpu_temp" not in result
        assert "disk_usage" not in result
        assert "current_track" not in result
        assert result["ram_usage"] == 38.5
        assert result["last_sync"] == "2026-02-24T09:00:00Z"
        assert result["status"] is True

    def test_mark_offline(self):
        """Mevcut branch offline olarak işaretlenir."""
        self.cache.update(1, _sample_payload())
        self.cache.mark_offline(1)

        result = self.cache.get(1)
        assert result is not None
        assert result["status"] is False

    def test_mark_offline_nonexistent(self):
        """Olmayan branch default davranışta entry oluşturmaz."""
        changed = self.cache.mark_offline(999)
        assert changed is False
        assert self.cache.get(999) is None

    def test_mark_offline_nonexistent_create_if_missing(self):
        """İstenirse olmayan branch için offline entry oluşturabilir."""
        changed = self.cache.mark_offline(999, create_if_missing=True)
        assert changed is True
        result = self.cache.get(999)
        assert result is not None
        assert result["status"] is False

    def test_get_all(self):
        """Tüm cache döner."""
        self.cache.update(1, _sample_payload())
        self.cache.update(2, _sample_payload())
        all_data = self.cache.get_all()
        assert len(all_data) == 2
        assert 1 in all_data
        assert 2 in all_data

    def test_stale_detection(self):
        """last_seen > timeout olan branch'ler tespit edilir."""
        # t=0'da güncelle
        with patch("backend.services.telemetry_cache.time.monotonic", return_value=0.0):
            self.cache.update(1, _sample_payload())
            self.cache.update(2, _sample_payload())

        # t=200 — sadece branch 1 tekrar heartbeat gönderdi
        with patch("backend.services.telemetry_cache.time.monotonic", return_value=200.0):
            self.cache.update(1, _sample_payload())

        # t=200'de kontrol: timeout=180 → branch 2 stale (200 - 0 = 200 > 180)
        with patch("backend.services.telemetry_cache.time.monotonic", return_value=200.0):
            stale = self.cache.get_stale_branch_ids(180.0)
            assert 2 in stale
            assert 1 not in stale

    def test_stale_excludes_already_offline(self):
        """Zaten offline olan branch'ler stale listesine dahil edilmez."""
        with patch("backend.services.telemetry_cache.time.monotonic", return_value=0.0):
            self.cache.update(1, _sample_payload())

        # Mark offline
        self.cache.mark_offline(1)

        with patch("backend.services.telemetry_cache.time.monotonic", return_value=300.0):
            stale = self.cache.get_stale_branch_ids(180.0)
            assert 1 not in stale  # Zaten offline, tekrar bildirilmeye gerek yok

    def test_evict_removes_stale_offline(self):
        """Offline TTL aşılmış kayıtlar evict edilir."""
        with patch("backend.services.telemetry_cache.time.monotonic", return_value=0.0):
            self.cache.update(1, _sample_payload())
            self.cache.mark_offline(1)
        with patch("backend.services.telemetry_cache.time.monotonic", return_value=100.0):
            self.cache.update(2, _sample_payload())
            self.cache.mark_offline(2)

        with patch("backend.services.telemetry_cache.time.monotonic", return_value=120.0):
            removed = self.cache.evict(offline_ttl_seconds=30.0, max_branches=100)

        assert removed == 1
        assert self.cache.get(1) is None
        assert self.cache.get(2) is not None

    def test_evict_enforces_max_branches(self):
        """Üst sınır aşılırsa en eski kayıtlar silinir."""
        with patch("backend.services.telemetry_cache.time.monotonic", return_value=1.0):
            self.cache.update(1, _sample_payload())
        with patch("backend.services.telemetry_cache.time.monotonic", return_value=2.0):
            self.cache.update(2, _sample_payload())
        with patch("backend.services.telemetry_cache.time.monotonic", return_value=3.0):
            self.cache.update(3, _sample_payload())

        removed = self.cache.evict(offline_ttl_seconds=-1.0, max_branches=2)

        assert removed == 1
        assert self.cache.get(1) is None
        assert len(self.cache.get_all()) == 2

    def test_update_keeps_previous_values_when_new_payload_invalid(self):
        """Yeni payload bozuk olsa da önceki sağlıklı alanlar korunur."""
        self.cache.update(
            1,
            {
                "status": True,
                "current_track": "summer_hit.mp3",
                "cpu_temp": 42.0,
            },
        )
        self.cache.update(
            1,
            {"cpu_temp": "not-a-number", "current_track": "x" * 600},
            max_string_length=512,
            force_status=True,
        )

        result = self.cache.get(1)
        assert result is not None
        assert result["status"] is True
        assert result["cpu_temp"] == 42.0
        assert result["current_track"] == "summer_hit.mp3"

    def test_clear(self):
        """Test amaçlı clear() sonrası cache boş."""
        self.cache.update(1, _sample_payload())
        self.cache.clear()
        assert self.cache.get_all() == {}


# ═══════════════════════════════════════════════════════════════
# 2. Topic Parsing Unit Tests
# ═══════════════════════════════════════════════════════════════


class TestTopicParsing:
    """MQTT topic parse fonksiyonu testleri."""

    def test_valid_status_topic(self):
        result = parse_topic("announceflow/default/42/status")
        assert result is not None
        tenant, branch_id, msg_type = result
        assert tenant == "default"
        assert branch_id == 42
        assert msg_type == "status"

    def test_valid_lwt_topic(self):
        result = parse_topic("announceflow/acme-corp/7/lwt")
        assert result is not None
        _, branch_id, msg_type = result
        assert branch_id == 7
        assert msg_type == "lwt"

    def test_invalid_topic_wrong_prefix(self):
        assert parse_topic("other/default/1/status") is None

    def test_invalid_topic_non_integer_branch(self):
        assert parse_topic("announceflow/default/abc/status") is None

    def test_invalid_topic_missing_segment(self):
        assert parse_topic("announceflow/1/status") is None

    def test_invalid_topic_unknown_type(self):
        assert parse_topic("announceflow/default/1/command") is None

    def test_empty_topic(self):
        assert parse_topic("") is None


# ═══════════════════════════════════════════════════════════════
# 3. Payload Parsing Unit Tests
# ═══════════════════════════════════════════════════════════════


class TestPayloadParsing:
    """JSON payload parse testleri."""

    def test_valid_json_bytes(self):
        raw = json.dumps(_sample_payload()).encode("utf-8")
        result = parse_payload(raw)
        assert result is not None
        assert result["cpu_temp"] == 52.1

    def test_valid_json_string(self):
        raw = json.dumps({"status": True})
        result = parse_payload(raw)
        assert result == {"status": True}

    def test_invalid_json(self):
        assert parse_payload(b"not json at all") is None

    def test_invalid_utf8(self):
        assert parse_payload(b"\xff\xfe") is None

    def test_json_array_rejected(self):
        assert parse_payload(json.dumps([1, 2, 3])) is None


# ═══════════════════════════════════════════════════════════════
# 4. HeartbeatService Integration Tests (DB)
# ═══════════════════════════════════════════════════════════════


class TestHeartbeatServiceDB:
    """
    HeartbeatService'in DB etkileşimini test eder.

    conftest.py'deki test_session_factory mock'lanarak
    background task session yönetimi simüle edilir.
    """

    @pytest.fixture(autouse=True)
    def _clean_cache(self):
        """Her test öncesi global telemetry_cache'i temizle."""
        telemetry_cache.clear()
        yield
        telemetry_cache.clear()

    async def test_handle_status_sets_online(
        self, db_session: AsyncSession, test_branch: Branch
    ):
        """Status mesajı gelince DB'de is_online=True olur."""
        # test_branch başlangıçta is_online=False
        assert test_branch.is_online is False

        topic = f"announceflow/default/{test_branch.id}/status"
        payload = json.dumps(_sample_payload())

        # Background task session'ı test session factory'ye yönlendir
        from tests.conftest import test_session_factory

        with patch(
            "backend.services.heartbeat_service.async_session_factory",
            test_session_factory,
        ):
            await heartbeat_service.handle_status_message(topic, payload)

        # DB kontrolü
        await db_session.refresh(test_branch)
        assert test_branch.is_online is True

        # Cache kontrolü
        cached = telemetry_cache.get(test_branch.id)
        assert cached is not None
        assert cached["status"] is True
        assert cached["current_track"] == "summer_hit.mp3"

    async def test_handle_lwt_sets_offline(
        self, db_session: AsyncSession, test_branch: Branch
    ):
        """LWT mesajı gelince DB'de is_online=False olur."""
        # Önce online yap
        test_branch.is_online = True
        await db_session.commit()

        topic = f"announceflow/default/{test_branch.id}/lwt"

        from tests.conftest import test_session_factory

        with patch(
            "backend.services.heartbeat_service.async_session_factory",
            test_session_factory,
        ):
            await heartbeat_service.handle_lwt_message(topic)

        await db_session.refresh(test_branch)
        assert test_branch.is_online is False

        # Cache'de de offline
        cached = telemetry_cache.get(test_branch.id)
        assert cached is not None
        assert cached["status"] is False

    async def test_handle_status_invalid_topic_ignored(self):
        """Geçersiz topic güvenli şekilde ignore edilir — hata fırlatmaz."""
        await heartbeat_service.handle_status_message("invalid/topic", b"{}")

    async def test_handle_status_invalid_payload_ignored(
        self, db_session: AsyncSession, test_branch: Branch,
    ):
        """Geçersiz JSON payload olsa da branch canlı (online) kabul edilir."""
        topic = f"announceflow/default/{test_branch.id}/status"
        from tests.conftest import test_session_factory

        with patch(
            "backend.services.heartbeat_service.async_session_factory",
            test_session_factory,
        ):
            await heartbeat_service.handle_status_message(topic, b"not json")

        await db_session.refresh(test_branch)
        assert test_branch.is_online is True

        cached = telemetry_cache.get(test_branch.id)
        assert cached is not None
        assert cached["status"] is True
        assert "last_seen" in cached
        assert "cpu_temp" not in cached

    async def test_handle_status_unknown_branch_not_cached(self):
        """DB'de olmayan branch için cache yazımı yapılmaz."""
        unknown_branch_id = 999_999
        topic = f"announceflow/default/{unknown_branch_id}/status"
        payload = json.dumps(_sample_payload())
        from tests.conftest import test_session_factory

        with patch(
            "backend.services.heartbeat_service.async_session_factory",
            test_session_factory,
        ):
            await heartbeat_service.handle_status_message(topic, payload)

        assert telemetry_cache.get(unknown_branch_id) is None

    async def test_handle_lwt_unknown_branch_not_cached(self):
        """DB'de olmayan branch için LWT cache entry açmaz."""
        unknown_branch_id = 888_888
        topic = f"announceflow/default/{unknown_branch_id}/lwt"
        from tests.conftest import test_session_factory

        with patch(
            "backend.services.heartbeat_service.async_session_factory",
            test_session_factory,
        ):
            await heartbeat_service.handle_lwt_message(topic)

        assert telemetry_cache.get(unknown_branch_id) is None

    async def test_handle_status_drops_oversized_values_but_keeps_alive(
        self, db_session: AsyncSession, test_branch: Branch
    ):
        """Aşırı büyük string alanı drop edilir, liveness korunur."""
        topic = f"announceflow/default/{test_branch.id}/status"
        payload = json.dumps(
            {
                "status": True,
                "current_track": "x" * 2000,
                "cpu_temp": 55.0,
            }
        )
        from tests.conftest import test_session_factory

        with (
            patch(
                "backend.services.heartbeat_service.async_session_factory",
                test_session_factory,
            ),
            patch.object(
                heartbeat_service.settings,
                "MQTT_TELEMETRY_MAX_STRING_LENGTH",
                512,
            ),
        ):
            await heartbeat_service.handle_status_message(topic, payload)

        await db_session.refresh(test_branch)
        assert test_branch.is_online is True
        cached = telemetry_cache.get(test_branch.id)
        assert cached is not None
        assert cached["status"] is True
        assert cached["cpu_temp"] == 55.0
        assert "current_track" not in cached

    async def test_reap_stale_branches(
        self, db_session: AsyncSession, test_branch: Branch
    ):
        """Reaper: 3 dk'dan eski heartbeat → toplu offline."""
        # Branch'ı online yap
        test_branch.is_online = True
        await db_session.commit()

        # Eski bir heartbeat ekle (t=0)
        with patch(
            "backend.services.telemetry_cache.time.monotonic", return_value=0.0
        ):
            telemetry_cache.update(test_branch.id, _sample_payload())

        from tests.conftest import test_session_factory

        # t=200 → 200 > 180 sn timeout → stale
        with (
            patch(
                "backend.services.telemetry_cache.time.monotonic", return_value=200.0
            ),
            patch(
                "backend.services.heartbeat_service.async_session_factory",
                test_session_factory,
            ),
        ):
            count = await heartbeat_service.reap_stale_branches()
            assert count >= 1

        await db_session.refresh(test_branch)
        assert test_branch.is_online is False

    async def test_reaper_runs_eviction_even_without_stale(self):
        """Stale yokken bile max-entries eviction uygulanır."""
        with patch("backend.services.telemetry_cache.time.monotonic", return_value=1.0):
            telemetry_cache.update(1, _sample_payload())
        with patch("backend.services.telemetry_cache.time.monotonic", return_value=2.0):
            telemetry_cache.update(2, _sample_payload())
        with patch("backend.services.telemetry_cache.time.monotonic", return_value=3.0):
            telemetry_cache.update(3, _sample_payload())

        with (
            patch.object(heartbeat_service.settings, "MQTT_HEARTBEAT_TIMEOUT_SECONDS", 300),
            patch.object(
                heartbeat_service.settings,
                "MQTT_TELEMETRY_CACHE_MAX_BRANCHES",
                2,
            ),
            patch.object(
                heartbeat_service.settings,
                "MQTT_TELEMETRY_OFFLINE_TTL_SECONDS",
                -1,
            ),
        ):
            count = await heartbeat_service.reap_stale_branches()

        assert count == 0
        assert telemetry_cache.get(1) is None
        assert len(telemetry_cache.get_all()) == 2


# ═══════════════════════════════════════════════════════════════
# 5. BranchRepository Heartbeat Tests
# ═══════════════════════════════════════════════════════════════


class TestBranchRepositoryHeartbeat:
    """Repository katmanı heartbeat metotları."""

    async def test_set_online_status_true(
        self, db_session: AsyncSession, test_branch: Branch
    ):
        repo = BranchRepository(db_session)
        result = await repo.set_online_status(test_branch.id, True)
        assert result is True

        await db_session.refresh(test_branch)
        assert test_branch.is_online is True

    async def test_set_online_status_nonexistent(self, db_session: AsyncSession):
        repo = BranchRepository(db_session)
        result = await repo.set_online_status(99999, True)
        assert result is False

    async def test_set_bulk_offline(
        self, db_session: AsyncSession, test_branch: Branch
    ):
        # Önce online yap
        test_branch.is_online = True
        await db_session.flush()

        repo = BranchRepository(db_session)
        count = await repo.set_bulk_offline([test_branch.id])
        assert count == 1

        await db_session.refresh(test_branch)
        assert test_branch.is_online is False

    async def test_set_bulk_offline_empty_list(self, db_session: AsyncSession):
        repo = BranchRepository(db_session)
        count = await repo.set_bulk_offline([])
        assert count == 0

    async def test_set_bulk_offline_already_offline(
        self, db_session: AsyncSession, test_branch: Branch
    ):
        """Zaten offline olan branch tekrar offline yapılmaz."""
        assert test_branch.is_online is False  # conftest default
        repo = BranchRepository(db_session)
        count = await repo.set_bulk_offline([test_branch.id])
        assert count == 0  # WHERE is_online=True filtresi nedeniyle


# ═══════════════════════════════════════════════════════════════
# 6. Telemetry Router (API) Tests
# ═══════════════════════════════════════════════════════════════


class TestTelemetryRouter:
    """Dashboard telemetri endpoint testleri."""

    @pytest.fixture(autouse=True)
    def _clean_cache(self):
        telemetry_cache.clear()
        yield
        telemetry_cache.clear()

    async def test_get_all_telemetry_admin(
        self, client: AsyncClient, admin_user: User
    ):
        """Admin tüm telemetri verisini okuyabilir."""
        telemetry_cache.update(1, _sample_payload())
        token = _admin_token(admin_user)

        resp = await client.get(
            "/api/v1/admin/telemetry",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "branches" in body
        assert 1 in [int(k) for k in body["branches"]] or "1" in body["branches"]

    async def test_get_all_telemetry_forbidden_for_user(
        self, client: AsyncClient, test_user: User
    ):
        """Normal user (is_vendor_admin=False) → 403."""
        token = _user_token(test_user)
        resp = await client.get(
            "/api/v1/admin/telemetry",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_get_all_telemetry_no_auth(self, client: AsyncClient):
        """Token olmadan → 401."""
        resp = await client.get("/api/v1/admin/telemetry")
        assert resp.status_code == 401

    async def test_get_branch_telemetry(
        self, client: AsyncClient, admin_user: User
    ):
        """Tek branch telemetri verisi."""
        telemetry_cache.update(42, _sample_payload())
        token = _admin_token(admin_user)

        resp = await client.get(
            "/api/v1/admin/telemetry/42",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["branch_id"] == 42
        assert body["telemetry"]["cpu_temp"] == 52.1

    async def test_get_branch_telemetry_not_found(
        self, client: AsyncClient, admin_user: User
    ):
        """Cache'de olmayan branch → 404."""
        token = _admin_token(admin_user)
        resp = await client.get(
            "/api/v1/admin/telemetry/999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
