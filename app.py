#!/usr/bin/env python3
import os

from attendance_app import create_app
from attendance_app.config import CSV_EXPORT_MAX_DAYS
from attendance_app.extensions import db
from attendance_app.models import AuditLog, Break, Shift, User
from attendance_app.services.audit_service import log_audit
from attendance_app.utils.datetime_utils import (
    ensure_aware,
    fmt_date_ja,
    fmt_dt,
    fmt_hms,
    format_local_form_value,
    parse_local_datetime,
)
from attendance_app.utils.security import verify_csrf
from attendance_app.utils.validators import ensure_valid_range

app = create_app()

__all__ = [
    "app",
    "db",
    "User",
    "Shift",
    "Break",
    "AuditLog",
    "ensure_aware",
    "ensure_valid_range",
    "parse_local_datetime",
    "format_local_form_value",
    "log_audit",
    "verify_csrf",
    "fmt_dt",
    "fmt_hms",
    "fmt_date_ja",
    "CSV_EXPORT_MAX_DAYS",
]


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        debug=env_bool("FLASK_DEBUG", False),
    )
