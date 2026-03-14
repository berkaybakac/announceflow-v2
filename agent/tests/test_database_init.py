"""Kritik Yol Testi: init_db() Idempotency ve WAL Mode.

Bu test, cihazın çökmesini engelleyen iki kritik şeyi kanıtlar:
1. init_db() arka arkaya çalıştırılınca hata fırlatmaz (idempotent)
2. WAL mode aktif — SD kart koruması sağlanıyor
3. 4 tablo eksiksiz oluşuyor
4. Config varsayılan değerleri doğru yerleşiyor
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile

import pytest
import pytest_asyncio

# --- Test icin DB_PATH'i gecici dizine yonlendir ---
# Settings import edilmeden ONCE env variable set edilmeli
_test_db_dir = tempfile.mkdtemp()
_test_db_path = os.path.join(_test_db_dir, "test_agent.db")
os.environ["DB_PATH"] = _test_db_path


from agent.core import database  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _clean_db():
    """Her testten once DB'yi sifirla."""
    # Singleton'i sifirla
    database._connection = None

    # Eski test DB'sini sil
    for suffix in ("", "-wal", "-shm"):
        path = _test_db_path + suffix
        if os.path.exists(path):
            os.remove(path)

    yield

    # Testten sonra temizle
    await database.close_db()
    database._connection = None


class TestInitDbIdempotency:
    """init_db() birden fazla kez çalıştırılabilmeli."""

    @pytest.mark.asyncio
    async def test_first_init_creates_tables(self) -> None:
        """İlk init_db() çağrısı 4 tabloyu oluşturmalı."""
        await database.init_db()

        db = await database.get_db()
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]

        expected = ["config", "local_media", "local_schedules", "prayer_times"]
        for table in expected:
            assert table in tables, f"'{table}' tablosu bulunamadı"

    @pytest.mark.asyncio
    async def test_second_init_no_error(self) -> None:
        """İkinci init_db() çağrısı hata fırlatmamalı (IF NOT EXISTS)."""
        await database.init_db()

        # İkinci kez — hata fırlatmamalı
        await database.init_db()

        # Tablolar hala orada mı?
        db = await database.get_db()
        cursor = await db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
            "AND name IN ('config', 'local_media', 'local_schedules', 'prayer_times')"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 4, "4 tablo olmalıydı"

    @pytest.mark.asyncio
    async def test_config_defaults_idempotent(self) -> None:
        """init_db() iki kez çalışınca config değerleri değişmemeli."""
        await database.init_db()

        db = await database.get_db()

        # Bir config değerini değiştir
        await db.execute(
            "UPDATE config SET value = '09:00' WHERE key = 'work_start'"
        )
        await db.commit()

        # Singleton'ı koruyarak ikinci init
        await database.init_db()

        # INSERT OR IGNORE — mevcut değer korunmalı
        cursor = await db.execute(
            "SELECT value FROM config WHERE key = 'work_start'"
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == "09:00", (
            "INSERT OR IGNORE mevcut değeri ezmemeli — "
            f"beklenen '09:00', alınan '{row[0]}'"
        )


class TestWalMode:
    """WAL mode aktif olmalı."""

    @pytest.mark.asyncio
    async def test_wal_mode_active(self) -> None:
        """PRAGMA journal_mode = WAL döndürmeli."""
        await database.init_db()

        db = await database.get_db()
        cursor = await db.execute("PRAGMA journal_mode")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0].lower() == "wal", (
            f"WAL mode aktif olmalıydı, '{row[0]}' döndü"
        )


class TestConfigDefaults:
    """Varsayılan config değerleri doğru yerleşmeli."""

    @pytest.mark.asyncio
    async def test_all_default_keys_present(self) -> None:
        """Tüm varsayılan config key'leri mevcut olmalı."""
        await database.init_db()

        db = await database.get_db()
        cursor = await db.execute("SELECT key FROM config ORDER BY key")
        keys = {row[0] for row in await cursor.fetchall()}

        expected_keys = {
            "work_start",
            "work_end",
            "volume_music",
            "volume_announce",
            "prayer_margin",
            "loop_active",
            "kill_active",
            "schema_version",
        }

        assert expected_keys == keys, (
            f"Eksik key'ler: {expected_keys - keys}, "
            f"Fazla key'ler: {keys - expected_keys}"
        )

    @pytest.mark.asyncio
    async def test_schema_version_is_set(self) -> None:
        """schema_version config tablosunda doğru değerde olmalı."""
        await database.init_db()

        db = await database.get_db()
        cursor = await db.execute(
            "SELECT value FROM config WHERE key = 'schema_version'"
        )
        row = await cursor.fetchone()

        assert row is not None, "schema_version key'i bulunamadı"
        assert row[0] == str(database.CURRENT_SCHEMA_VERSION), (
            f"schema_version={row[0]}, beklenen={database.CURRENT_SCHEMA_VERSION}"
        )


class TestTableSchema:
    """Tablo şemaları doğru olmalı."""

    @pytest.mark.asyncio
    async def test_local_media_type_constraint(self) -> None:
        """local_media.type sadece 'MUSIC' veya 'ANONS' kabul etmeli."""
        await database.init_db()

        db = await database.get_db()

        # Geçerli tip
        await db.execute(
            "INSERT INTO local_media (id, file_name, file_hash, type, local_path) "
            "VALUES (100, 'test.mp3', 'abc123', 'MUSIC', '/data/test.mp3')"
        )
        await db.commit()

        # Geçersiz tip — CHECK constraint hatası vermeli
        with pytest.raises(Exception):
            await db.execute(
                "INSERT INTO local_media (id, file_name, file_hash, type, local_path) "
                "VALUES (101, 'test2.mp3', 'def456', 'INVALID', '/data/test2.mp3')"
            )
            await db.commit()


class TestForeignKeyEnforcement:
    """SQLite foreign key enforcement acik olmali."""

    @pytest.mark.asyncio
    async def test_foreign_keys_pragma_active(self) -> None:
        """PRAGMA foreign_keys = 1 donmeli."""
        await database.init_db()

        db = await database.get_db()
        cursor = await db.execute("PRAGMA foreign_keys")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 1, "SQLite foreign key enforcement acik olmali"

    @pytest.mark.asyncio
    async def test_local_schedule_requires_existing_media(self) -> None:
        """local_schedules.media_id mevcut olmayan local_media.id'ye baglanamamali."""
        await database.init_db()

        db = await database.get_db()
        with pytest.raises(sqlite3.IntegrityError):
            await db.execute(
                "INSERT INTO local_schedules (id, media_id, cron_expression, play_at, end_time) "
                "VALUES (500, 999999, NULL, NULL, NULL)"
            )
            await db.commit()


class TestConnectionSafety:
    """Singleton connection kilit ve hata yolu guvenligi."""

    @pytest.mark.asyncio
    async def test_get_db_concurrent_calls_create_single_connection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Eszamanli get_db() cagrilari tek bir baglanti olusturmali."""

        class FakeConnection:
            def __init__(self) -> None:
                self.row_factory = None
                self.closed = False

            async def execute(self, _sql: str) -> None:
                await asyncio.sleep(0.01)

            async def close(self) -> None:
                self.closed = True

        created: list[FakeConnection] = []

        async def fake_connect(_path: str) -> FakeConnection:
            await asyncio.sleep(0.02)
            conn = FakeConnection()
            created.append(conn)
            return conn

        monkeypatch.setattr(database.aiosqlite, "connect", fake_connect)
        database._connection = None

        db_list = await asyncio.gather(
            database.get_db(),
            database.get_db(),
            database.get_db(),
            database.get_db(),
        )

        assert len(created) == 1, "Tek bir sqlite baglantisi olusmali"
        assert all(db is db_list[0] for db in db_list)
        assert database._connection is db_list[0]

    @pytest.mark.asyncio
    async def test_get_db_closes_connection_on_pragma_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PRAGMA adiminda hata olursa baglanti kapatilip tekrar raise edilmeli."""

        class FailingConnection:
            def __init__(self) -> None:
                self.row_factory = None
                self.closed = False

            async def execute(self, _sql: str) -> None:
                raise RuntimeError("pragma failed")

            async def close(self) -> None:
                self.closed = True

        failing_conn = FailingConnection()

        async def fake_connect(_path: str) -> FailingConnection:
            return failing_conn

        monkeypatch.setattr(database.aiosqlite, "connect", fake_connect)
        database._connection = None

        with pytest.raises(RuntimeError, match="pragma failed"):
            await database.get_db()

        assert failing_conn.closed is True
        assert database._connection is None
