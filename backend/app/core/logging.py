"""Logging configuration: plain text or JSON lines (`LOG_FORMAT=json`)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """One JSON object per line; never includes request bodies or secrets."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(log_format: str = "text", debug: bool = False) -> None:
    root = logging.getLogger()
    level = logging.DEBUG if debug else logging.INFO
    root.setLevel(level)
    handler = logging.StreamHandler()
    if log_format.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    # Replace existing handlers so re-configuration (tests) does not duplicate output.
    root.handlers[:] = [handler]
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING if not debug else logging.INFO)
