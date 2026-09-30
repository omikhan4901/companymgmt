"""Structured JSON logs (Cloud Logging reads `severity` and `message`)."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from app.core import context

_SKIP = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        info = context.current()
        entry: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": info.request_id or None,
            # Tenant id only; never personal data in logs.
            "tenant_id": str(info.tenant_id) if info.tenant_id else None,
        }
        for key, value in record.__dict__.items():
            if key not in _SKIP and not key.startswith("_"):
                entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str, ensure_ascii=False)


def configure_logging(env: str) -> None:
    root = logging.getLogger()
    if getattr(root, "_cm_configured", False):
        return
    handler = logging.StreamHandler(sys.stdout)
    if env in ("staging", "prod"):
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.handlers = [handler]
    root.setLevel(logging.INFO if env != "test" else logging.WARNING)
    root._cm_configured = True  # type: ignore[attr-defined]
