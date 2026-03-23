from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from agent import scheduler as scheduler_module


@pytest.fixture(autouse=True)
def _reset_scheduler_singleton() -> Generator[None, None, None]:
    scheduler_module._scheduler = None
    yield
    scheduler_module._scheduler = None


def test_create_engine_with_wal_sets_pragmas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "scheduler_jobs.db"
    monkeypatch.setattr(
        scheduler_module.agent_settings,
        "DB_PATH",
        str(db_path),
    )

    engine = cast(Engine, scheduler_module._create_engine_with_wal())
    with engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar_one()
        busy_timeout = conn.execute(text("PRAGMA busy_timeout")).scalar_one()

    assert str(journal_mode).lower() == "wal"
    assert int(busy_timeout) == 5000
    engine.dispose()


def test_get_scheduler_creates_singleton_once() -> None:
    fake_scheduler = MagicMock()
    fake_scheduler.running = False
    fake_jobstore = object()

    with (
        patch.object(
            scheduler_module,
            "_create_engine_with_wal",
            return_value="fake-engine",
        ) as engine_mock,
        patch.object(
            scheduler_module,
            "SQLAlchemyJobStore",
            return_value=fake_jobstore,
        ) as jobstore_mock,
        patch.object(
            scheduler_module,
            "BackgroundScheduler",
            return_value=fake_scheduler,
        ) as scheduler_ctor_mock,
    ):
        first = scheduler_module.get_scheduler()
        second = scheduler_module.get_scheduler()

    assert first is fake_scheduler
    assert second is fake_scheduler
    engine_mock.assert_called_once()
    jobstore_mock.assert_called_once_with(engine="fake-engine")
    scheduler_ctor_mock.assert_called_once()


@pytest.mark.asyncio
async def test_start_scheduler_returns_early_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(scheduler_module.agent_settings, "SCHEDULER_ENABLED", False)

    with patch.object(scheduler_module, "get_scheduler") as get_scheduler_mock:
        await scheduler_module.start_scheduler()

    get_scheduler_mock.assert_not_called()


@pytest.mark.asyncio
async def test_start_scheduler_does_not_restart_running_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(scheduler_module.agent_settings, "SCHEDULER_ENABLED", True)
    fake_scheduler = MagicMock()
    fake_scheduler.running = True

    with (
        patch.object(scheduler_module, "get_scheduler", return_value=fake_scheduler),
        patch(
            "agent.scheduler.asyncio.to_thread",
            new=AsyncMock(),
        ) as to_thread_mock,
    ):
        await scheduler_module.start_scheduler()

    to_thread_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_scheduler_starts_when_not_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(scheduler_module.agent_settings, "SCHEDULER_ENABLED", True)
    fake_scheduler = MagicMock()
    fake_scheduler.running = False

    with (
        patch.object(scheduler_module, "get_scheduler", return_value=fake_scheduler),
        patch(
            "agent.scheduler.asyncio.to_thread",
            new=AsyncMock(),
        ) as to_thread_mock,
    ):
        await scheduler_module.start_scheduler()

    to_thread_mock.assert_awaited_once_with(fake_scheduler.start, False)


@pytest.mark.asyncio
async def test_shutdown_scheduler_stops_running_instance_and_resets_singleton() -> None:
    fake_scheduler = MagicMock()
    fake_scheduler.running = True
    scheduler_module._scheduler = fake_scheduler

    with patch(
        "agent.scheduler.asyncio.to_thread",
        new=AsyncMock(),
    ) as to_thread_mock:
        await scheduler_module.shutdown_scheduler()

    to_thread_mock.assert_awaited_once_with(fake_scheduler.shutdown, False)
    assert scheduler_module._scheduler is None


@pytest.mark.asyncio
async def test_shutdown_scheduler_noop_when_already_stopped() -> None:
    fake_scheduler = MagicMock()
    fake_scheduler.running = False
    scheduler_module._scheduler = fake_scheduler

    with patch(
        "agent.scheduler.asyncio.to_thread",
        new=AsyncMock(),
    ) as to_thread_mock:
        await scheduler_module.shutdown_scheduler()

    to_thread_mock.assert_not_awaited()
    assert scheduler_module._scheduler is None


@pytest.mark.asyncio
async def test_shutdown_scheduler_noop_when_singleton_missing() -> None:
    scheduler_module._scheduler = None
    with patch(
        "agent.scheduler.asyncio.to_thread",
        new=AsyncMock(),
    ) as to_thread_mock:
        await scheduler_module.shutdown_scheduler()

    to_thread_mock.assert_not_awaited()
    assert scheduler_module._scheduler is None
