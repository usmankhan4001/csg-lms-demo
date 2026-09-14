"""
Structured JSON Logger & Tracing Context for CSG LMS.
"""

import json
import logging
import sys
import time
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional

correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
tenant_org_id_var: ContextVar[Optional[int]] = ContextVar("tenant_org_id", default=None)
acting_user_id_var: ContextVar[Optional[int]] = ContextVar("acting_user_id", default=None)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get(),
            "org_id": tenant_org_id_var.get(),
            "user_id": acting_user_id_var.get(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_structured_logging(level: int = logging.INFO):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # Remove existing handlers to avoid duplicates
    root_logger.handlers = [handler]
    logging.getLogger("uvicorn.access").handlers = [handler]
