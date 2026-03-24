import time
from datetime import datetime, timezone
from unittest.mock import patch

from httpx import AsyncClient  # noqa: TC002

from backend.core.security import create_access_token
from backend.models.branch import Branch
from backend.models.user import User
from backend.services.log_service import FloodProtector

# ── Helpers ─────────────────────────────────────────────────────


def _device_token(branch: Branch) -> str:
    """Şube için geçerli device JWT üretir."""
    return create_access_token({"sub": str(branch.id), "type": "device"})


def _user_token(user: User) -> str:
    """Kullanıcı için geçerli user JWT üretir."""
    return create_access_token({"sub": str(user.id), "type": "user"})


def _make_log_payload(
    message: str = "test log",
    level: str = "INFO",
    count: int = 1,
) -> dict:
    """Log batch payload üretir."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "logs": [
            {"level": level, "message": message, "created_at": now}
            for _ in range(count)
        ]
    }


# ── Auth Tests ──────────────────────────────────────────────────


class TestLogIngestionAuth:
    """Log endpoint'inin sadece device JWT ile erişilebilir olduğunu doğrular."""

    async def test_ingest_requires_device_token(
        self, client: AsyncClient, test_user: User
    ):
        """User JWT ile log gönderilmeye çalışılırsa → 401."""
        token = _user_token(test_user)
        resp = await client.post(
            "/api/v1/logs/",
            json=_make_log_payload(),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    async def test_ingest_no_token(self, client: AsyncClient):
        """Token olmadan erişim → 401."""
        resp = await client.post("/api/v1/logs/", json=_make_log_payload())
        assert resp.status_code == 401

    async def test_ingest_inactive_branch(
        self, client: AsyncClient, inactive_branch: Branch
    ):
        """Devre dışı şube token'ı ile log gönderilirse → 403."""
        token = _device_token(inactive_branch)
        resp = await client.post(
            "/api/v1/logs/",
            json=_make_log_payload(),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


# ── Ingestion Tests ─────────────────────────────────────────────


class TestLogIngestion:
    """Log kaydı ekleme işlevselliğini doğrular."""

    async def test_ingest_success(self, client: AsyncClient, test_branch: Branch):
        """Geçerli device JWT + batch payload → 201, kabul edilen sayı doğru."""
        token = _device_token(test_branch)
        payload = _make_log_payload(count=3)
        resp = await client.post(
            "/api/v1/logs/",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["accepted"] == 3

    async def test_ingest_empty_batch(self, client: AsyncClient, test_branch: Branch):
        """Boş log listesi → 201, 0 kayıt kabul edilir."""
        token = _device_token(test_branch)
        resp = await client.post(
            "/api/v1/logs/",
            json={"logs": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["accepted"] == 0

    async def test_ingest_invalid_level(
        self, client: AsyncClient, test_branch: Branch
    ):
        """Geçersiz log level → 422 validation error."""
        token = _device_token(test_branch)
        now = datetime.now(timezone.utc).isoformat()
        resp = await client.post(
            "/api/v1/logs/",
            json={"logs": [{"level": "INVALID", "message": "x", "created_at": now}]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    async def test_ingest_with_context(
        self, client: AsyncClient, test_branch: Branch
    ):
        """Context alanı (JSONB) olan log kaydı başarıyla kabul edilir."""
        token = _device_token(test_branch)
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "logs": [
                {
                    "level": "ERROR",
                    "message": "Connection timeout",
                    "context": {"host": "mqtt.example.com", "port": 1883, "retry": 3},
                    "created_at": now,
                }
            ]
        }
        resp = await client.post(
            "/api/v1/logs/",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["accepted"] == 1


# ── Flood Protection Tests ──────────────────────────────────────


class TestFloodProtection:
    """In-memory flood protection mekanizmasını doğrular."""

    async def test_flood_protection_throttles(
        self, client: AsyncClient, test_branch: Branch
    ):
        """
        Aynı mesaj 15 kez gönderildiğinde sadece 10'u kabul edilir.
        FloodProtector singleton state'i testler arası sızmasın diye
        time.monotonic mock'lanıyor.
        """
        token = _device_token(test_branch)

        # FloodProtector'ı taze instance ile değiştir
        fresh_flood = FloodProtector()
        with patch("backend.services.log_service._flood_protector", fresh_flood):
            payload = _make_log_payload(message="repeated error", count=15)
            resp = await client.post(
                "/api/v1/logs/",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["accepted"] == 10  # İlk 10 kabul, 5'i flood nedeniyle atıldı

    async def test_flood_protection_resets_after_window(
        self, client: AsyncClient, test_branch: Branch
    ):
        """
        Flood tetiklendikten sonra zaman penceresi (1 saniye) geçince
        kilitlenme açılır ve aynı mesaj tekrar kabul edilir.
        """
        token = _device_token(test_branch)
        msg = "window reset test"

        fresh_flood = FloodProtector()
        with patch("backend.services.log_service._flood_protector", fresh_flood):
            # 1) Limit'i doldur (10 kayıt)
            payload_fill = _make_log_payload(message=msg, count=10)
            resp1 = await client.post(
                "/api/v1/logs/",
                json=payload_fill,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp1.json()["accepted"] == 10

            # 2) Limit dolu — 11. kayıt reddedilmeli
            payload_overflow = _make_log_payload(message=msg, count=1)
            resp2 = await client.post(
                "/api/v1/logs/",
                json=payload_overflow,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp2.json()["accepted"] == 0

            # 3) Zaman penceresini ileri sar (1.1 saniye)
            original_monotonic = time.monotonic
            with patch(
                "backend.services.log_service.time.monotonic",
                side_effect=lambda: original_monotonic() + 1.1,
            ):
                # 4) Pencere geçti — aynı mesaj tekrar kabul edilmeli
                resp3 = await client.post(
                    "/api/v1/logs/",
                    json=payload_overflow,
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert resp3.json()["accepted"] == 1

    async def test_flood_different_messages_independent(
        self, client: AsyncClient, test_branch: Branch
    ):
        """Farklı mesajlar birbirinin flood sayacını etkilemez."""
        token = _device_token(test_branch)

        fresh_flood = FloodProtector()
        with patch("backend.services.log_service._flood_protector", fresh_flood):
            # Mesaj A: 10 kayıt → hepsi kabul
            resp_a = await client.post(
                "/api/v1/logs/",
                json=_make_log_payload(message="error A", count=10),
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp_a.json()["accepted"] == 10

            # Mesaj B: 5 kayıt → hepsi kabul (farklı mesaj, farklı sayaç)
            resp_b = await client.post(
                "/api/v1/logs/",
                json=_make_log_payload(message="error B", count=5),
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp_b.json()["accepted"] == 5

    def test_flood_evicts_stale_keys_from_memory(self):
        """
        Tekrarlanmayan mesaj anahtarları zaman penceresi geçince RAM'den temizlenir.
        Bu test _counters sözlüğünün sınırsız büyümemesini doğrular.
        """
        flood = FloodProtector()
        branch_id = 42

        with patch(
            "backend.services.log_service.time.monotonic",
            side_effect=[0.0, 0.0, 0.0, 0.0, 1.2],
        ):
            for idx in range(4):
                assert flood.is_allowed(branch_id, f"unique-{idx}") is True

            assert len(flood._counters) == 4

            # Sweep'i tetikleyen yeni istek.
            assert flood.is_allowed(branch_id, "trigger-sweep") is True

        assert set(flood._counters.keys()) == {(branch_id, "trigger-sweep")}
