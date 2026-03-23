from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio

from agent.core import database
from agent.core.repositories import (
    ConfigRepository,
    LocalMediaRepository,
    LocalScheduleRepository,
    PrayerTimeRepository,
)


@pytest_asyncio.fixture(autouse=True)
async def _isolated_agent_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "agent_repo_test.db"
    monkeypatch.setattr(database.agent_settings, "DB_PATH", str(db_path))

    await database.close_db()
    database._connection = None
    await database.init_db()

    yield

    await database.close_db()
    database._connection = None
    for suffix in ("", "-wal", "-shm"):
        path = str(db_path) + suffix
        if os.path.exists(path):
            os.remove(path)


@pytest.mark.asyncio
async def test_config_repository_get_set_get_all_and_set_many() -> None:
    repo = ConfigRepository()

    assert await repo.get("work_start") == "08:00"
    assert await repo.get("non_existing_key") is None

    await repo.set("work_start", "09:30")
    assert await repo.get("work_start") == "09:30"

    await repo.set_many(
        {
            "volume_music": "72",
            "volume_announce": "88",
            "custom_key": "custom_value",
        }
    )
    all_values = await repo.get_all()

    assert all_values["volume_music"] == "72"
    assert all_values["volume_announce"] == "88"
    assert all_values["custom_key"] == "custom_value"


@pytest.mark.asyncio
async def test_local_media_repository_upsert_lookup_and_delete() -> None:
    repo = LocalMediaRepository()

    await repo.upsert(
        media_id=1,
        file_name="song.mp3",
        file_hash="hash-1",
        media_type="MUSIC",
        local_path="/data/media/1.mp3",
    )

    by_id = await repo.get_by_id(1)
    assert by_id is not None
    assert by_id["file_name"] == "song.mp3"
    assert by_id["type"] == "MUSIC"

    by_hash = await repo.get_by_hash("hash-1")
    assert by_hash is not None
    assert by_hash["id"] == 1

    by_type = await repo.get_by_type("MUSIC")
    assert len(by_type) == 1
    assert by_type[0]["id"] == 1

    all_items = await repo.get_all()
    assert len(all_items) == 1

    await repo.upsert(
        media_id=1,
        file_name="song-updated.mp3",
        file_hash="hash-2",
        media_type="MUSIC",
        local_path="/data/media/1-updated.mp3",
    )
    updated = await repo.get_by_id(1)
    assert updated is not None
    assert updated["file_name"] == "song-updated.mp3"
    assert updated["file_hash"] == "hash-2"

    await repo.delete(1)
    assert await repo.get_by_id(1) is None


@pytest.mark.asyncio
async def test_local_schedule_repository_upsert_get_delete_and_delete_all() -> None:
    media_repo = LocalMediaRepository()
    schedule_repo = LocalScheduleRepository()

    await media_repo.upsert(
        media_id=101,
        file_name="anons.mp3",
        file_hash="anons-hash",
        media_type="ANONS",
        local_path="/data/media/101.mp3",
    )

    await schedule_repo.upsert(
        schedule_id=10,
        media_id=101,
        cron_expression="0 14 * * *",
        play_at=None,
        end_time=None,
    )
    await schedule_repo.upsert(
        schedule_id=11,
        media_id=101,
        cron_expression=None,
        play_at="2026-03-24T14:00:00+00:00",
        end_time="2026-03-24T14:00:30+00:00",
    )

    first = await schedule_repo.get_by_id(10)
    assert first is not None
    assert first["cron_expression"] == "0 14 * * *"

    all_items = await schedule_repo.get_all()
    assert len(all_items) == 2

    await schedule_repo.delete(10)
    assert await schedule_repo.get_by_id(10) is None
    assert len(await schedule_repo.get_all()) == 1

    await schedule_repo.delete_all()
    assert await schedule_repo.get_all() == []


@pytest.mark.asyncio
async def test_prayer_time_repository_bulk_range_and_delete_before() -> None:
    repo = PrayerTimeRepository()

    assert await repo.get_by_date("2026-03-20") is None
    initial_range = await repo.get_cached_range()
    assert initial_range["count"] == 0

    await repo.bulk_upsert(
        [
            {
                "date": "2026-03-20",
                "fajr": "05:10",
                "sunrise": "06:35",
                "dhuhr": "12:30",
                "asr": "15:45",
                "maghrib": "18:20",
                "isha": "19:40",
                "fetched_at": "2026-03-19T00:00:00Z",
            },
            {
                "date": "2026-03-21",
                "fajr": "05:09",
                "sunrise": "06:33",
                "dhuhr": "12:31",
                "asr": "15:46",
                "maghrib": "18:21",
                "isha": "19:41",
                "fetched_at": "2026-03-19T00:00:00Z",
            },
        ]
    )

    day = await repo.get_by_date("2026-03-20")
    assert day is not None
    assert day["maghrib"] == "18:20"

    cached_range = await repo.get_cached_range()
    assert cached_range == {
        "min_date": "2026-03-20",
        "max_date": "2026-03-21",
        "count": 2,
    }

    deleted = await repo.delete_before("2026-03-21")
    assert deleted == 1

    deleted_none = await repo.delete_before("2020-01-01")
    assert deleted_none == 0
