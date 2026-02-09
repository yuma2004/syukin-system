import csv
import json
from datetime import datetime, timezone
from io import StringIO

from sqlalchemy import func
from sqlalchemy.orm import selectinload

from ..config import LOCAL_TZ
from ..models import Shift, User
from ..utils.validators import ensure_valid_range


def generate_attendance_csv(start_date, end_date, user_username=None, user_email=None):
    start_date, end_date = ensure_valid_range(start_date, end_date)
    start_utc = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    end_utc = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)

    query = (
        Shift.query.options(selectinload(Shift.user), selectinload(Shift.breaks))
        .join(User)
        .filter(Shift.clock_in_at >= start_utc, Shift.clock_in_at <= end_utc)
    )
    if user_username:
        query = query.filter(User.username == user_username)
    elif user_email:
        query = query.filter(func.lower(User.email) == user_email)

    shifts = query.order_by(Shift.clock_in_at.asc()).all()

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "user_username",
            "user_email",
            "user_name",
            "shift_id",
            "clock_in_local",
            "clock_out_local",
            "worked_seconds",
            "worked_hms",
            "clock_in_utc",
            "clock_out_utc",
            "clock_in_ip",
            "clock_out_ip",
            "clock_in_ua",
            "clock_out_ua",
            "break_count",
            "breaks_total_seconds",
            "breaks_total_hms",
        ]
    )

    for shift in shifts:
        in_local = shift.clock_in_at.astimezone(LOCAL_TZ) if shift.clock_in_at else None
        out_local = shift.clock_out_at.astimezone(LOCAL_TZ) if shift.clock_out_at else None
        worked = shift.worked_seconds()
        break_seconds = shift.total_break_seconds()
        writer.writerow(
            [
                shift.user.username,
                shift.user.email or "",
                shift.user.name or "",
                shift.id,
                in_local.strftime("%Y-%m-%d %H:%M:%S") if in_local else "",
                out_local.strftime("%Y-%m-%d %H:%M:%S") if out_local else "",
                worked,
                f"{worked // 3600:02d}:{(worked % 3600) // 60:02d}:{worked % 60:02d}",
                shift.clock_in_at.isoformat() if shift.clock_in_at else "",
                shift.clock_out_at.isoformat() if shift.clock_out_at else "",
                shift.clock_in_ip or "",
                shift.clock_out_ip or "",
                shift.clock_in_ua or "",
                shift.clock_out_ua or "",
                len(shift.breaks),
                break_seconds,
                f"{break_seconds // 3600:02d}:{(break_seconds % 3600) // 60:02d}:{break_seconds % 60:02d}",
            ]
        )

    return buffer.getvalue().encode("utf-8-sig"), len(shifts)


def generate_audit_csv(logs):
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "created_at_local",
            "created_at_utc",
            "action",
            "user_username",
            "user_email",
            "user_name",
            "target_type",
            "target_id",
            "ip",
            "user_agent",
            "metadata_json",
            "signature",
        ]
    )

    for log in logs:
        local_ts = log.created_at.astimezone(LOCAL_TZ) if log.created_at else None
        created_local = local_ts.strftime("%Y-%m-%d %H:%M:%S") if local_ts else ""
        created_utc = log.created_at.isoformat() if log.created_at else ""
        try:
            metadata = json.loads(log.metadata_json) if log.metadata_json else {}
        except Exception:
            metadata = {"raw": log.metadata_json}
        metadata_json = json.dumps(metadata, ensure_ascii=False, separators=(",", ":")) if metadata else ""

        writer.writerow(
            [
                created_local,
                created_utc,
                log.action,
                log.user.username if log.user else "",
                log.user.email if log.user else "",
                log.user.name if log.user else "",
                log.target_type or "",
                log.target_id or "",
                log.ip or "",
                log.user_agent or "",
                metadata_json,
                log.signature or "",
            ]
        )

    return buffer.getvalue().encode("utf-8-sig")
