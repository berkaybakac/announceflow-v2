import json
import logging
import sys
from datetime import datetime, timezone
from threading import Lock
from typing import Any

_CONFIG_LOCK = Lock()
_CONFIGURED = False

_RESERVED_RECORD_KEYS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
}


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_KEYS:
                payload[key] = value

        return json.dumps(payload, default=str)


def _configure_manifest_logger_once() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    with _CONFIG_LOCK:
        if _CONFIGURED:
            return

        parent_logger = logging.getLogger("announceflow.manifest")
        parent_logger.setLevel(logging.INFO)
        parent_logger.propagate = False
        parent_logger.handlers.clear()

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonLogFormatter())
        parent_logger.addHandler(handler)

        _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_manifest_logger_once()
    logger = logging.getLogger(f"announceflow.manifest.{name}")
    logger.setLevel(logging.INFO)
    logger.propagate = True
    return logger
