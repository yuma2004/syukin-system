import csv
import json
from io import StringIO

from ..config import LOCAL_TZ
from ..models import Shift
from .shift_query_service import apply_shift_user_filters, build_shift_range_query


def generate_attendance_csv(start_date, end_date, user_username=None, user_email=None):
    query, start_date, end_date = build_shift_range_query(start_date, end_date)
    query = apply_shift_user_filters(query, user_username=user_username, user_email=user_email)

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
