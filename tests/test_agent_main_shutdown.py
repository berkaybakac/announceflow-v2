import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_agent_and_sigterm(
    *,
    env_overrides: dict[str, str],
    wait_before_signal: float,
    timeout_seconds: float = 5.0,
) -> tuple[int, str]:
    env = os.environ.copy()
    env.update(env_overrides)
    env.setdefault("PYTHONUNBUFFERED", "1")

    proc = subprocess.Popen(
        [sys.executable, "-m", "agent.main"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        time.sleep(wait_before_signal)
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        output = proc.communicate(timeout=2)[0]
        pytest.fail(
            "Agent SIGTERM sonrasi kapanmadi.\n"
            f"Output tail:\n{chr(10).join(output.splitlines()[-20:])}"
        )

    output = proc.communicate(timeout=2)[0]
    return proc.returncode, output


def _run_agent_until_exit(
    *,
    env_overrides: dict[str, str],
    timeout_seconds: float = 5.0,
) -> tuple[int, str]:
    env = os.environ.copy()
    env.update(env_overrides)
    env.setdefault("PYTHONUNBUFFERED", "1")

    proc = subprocess.Popen(
        [sys.executable, "-m", "agent.main"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        output = proc.communicate(timeout=2)[0]
        pytest.fail(
            "Agent max retry sonrasi cikmadi.\n"
            f"Output tail:\n{chr(10).join(output.splitlines()[-20:])}"
        )

    output = proc.communicate(timeout=2)[0]
    return proc.returncode, output


def test_sigterm_exits_while_waiting_for_missing_token(tmp_path: Path) -> None:
    missing_token_path = tmp_path / "device_token.txt"
    db_path = tmp_path / "agent_waiting.db"

    return_code, output = _run_agent_and_sigterm(
        env_overrides={
            "TOKEN_PATH": str(missing_token_path),
            "DB_PATH": str(db_path),
            "SCHEDULER_ENABLED": "false",
        },
        wait_before_signal=1.0,
    )

    assert return_code == 0
    assert "Agent kapatildi" in output


def test_boot_stops_after_max_token_retries(tmp_path: Path) -> None:
    missing_token_path = tmp_path / "device_token.txt"
    db_path = tmp_path / "agent_retry_limit.db"

    return_code, output = _run_agent_until_exit(
        env_overrides={
            "TOKEN_PATH": str(missing_token_path),
            "DB_PATH": str(db_path),
            "SCHEDULER_ENABLED": "false",
            "BOOT_TOKEN_RETRY_INTERVAL_SECONDS": "0.05",
            "BOOT_TOKEN_MAX_RETRIES": "2",
        },
        timeout_seconds=3.0,
    )

    assert return_code == 0
    assert "maksimum deneme sayisina ulasildi" in output
    assert "Boot sequence shutdown nedeniyle yarida kesildi" in output


def test_sigterm_exits_after_boot_ready(tmp_path: Path) -> None:
    token_path = tmp_path / "device_token.txt"
    token_path.write_text("test-device-token", encoding="utf-8")
    db_path = tmp_path / "agent_ready.db"

    return_code, output = _run_agent_and_sigterm(
        env_overrides={
            "TOKEN_PATH": str(token_path),
            "DB_PATH": str(db_path),
            "SCHEDULER_ENABLED": "false",
        },
        wait_before_signal=2.0,
    )

    assert return_code == 0
    assert "Agent kapatildi" in output
