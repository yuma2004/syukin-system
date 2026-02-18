from collections import defaultdict
from datetime import datetime, timedelta, timezone

from flask import abort

from ..config import LOCAL_TZ
from ..models import Shift, User
from .shift_query_service import apply_shift_user_filters, build_shift_range_query
from ..utils.datetime_utils import fmt_hms


def build_admin_overview(start_arg=None, end_arg=None, user_username="", include_candidates=False):
    now_local = datetime.now(LOCAL_TZ)
    default_end = now_local.date()
    default_start = default_end - timedelta(days=13)

    try:
        start_date = datetime.fromisoformat(start_arg).date() if start_arg else default_start
        end_date = datetime.fromisoformat(end_arg).date() if end_arg else default_end
    except ValueError:
        abort(400, "日付の形式が不正です。YYYY-MM-DD で指定してください。")

    query, start_date, end_date = build_shift_range_query(start_date, end_date)
    query = apply_shift_user_filters(query, user_username=user_username)

    shifts = query.order_by(Shift.clock_in_at.desc()).all()

    daily_buckets = defaultdict(lambda: {"seconds": 0, "count": 0})
    for shift in shifts:
        if not shift.clock_in_at:
            continue
        local_date = shift.clock_in_at.astimezone(LOCAL_TZ).date()
        bucket = daily_buckets[local_date]
        bucket["seconds"] += shift.worked_seconds()
        bucket["count"] += 1

    daily_totals = [
        {
            "date": date_key,
            "seconds": bucket["seconds"],
            "worked_hms": fmt_hms(bucket["seconds"]),
            "count": bucket["count"],
        }
        for date_key, bucket in sorted(daily_buckets.items(), reverse=True)
    ]

    context = {
        "shifts": shifts,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "user_username": user_username,
        "daily_totals": daily_totals,
    }
    if include_candidates:
        context["user_candidates"] = User.query.order_by(User.username.asc()).all()
    return context


def build_shift_edit_context(shift):
    from ..utils.datetime_utils import format_local_form_value

    break_entries = []
    ordered_breaks = sorted(
        shift.breaks,
        key=lambda br: (br.start_at or datetime.min.replace(tzinfo=timezone.utc)),
    )
    for br in ordered_breaks:
        break_entries.append(
            {
                "id": br.id,
                "start_form": format_local_form_value(br.start_at),
                "end_form": format_local_form_value(br.end_at),
                "start_utc": br.start_at.isoformat() if br.start_at else None,
                "end_utc": br.end_at.isoformat() if br.end_at else None,
                "is_open": br.end_at is None,
            }
        )

    return {
        "clock_in_form": format_local_form_value(shift.clock_in_at),
        "clock_out_form": format_local_form_value(shift.clock_out_at),
        "break_entries": break_entries,
    }


def build_shift_detail_payload(shift):
    from ..utils.datetime_utils import fmt_hms

    clock_in_local = shift.clock_in_at.astimezone(LOCAL_TZ) if shift.clock_in_at else None
    clock_out_local = shift.clock_out_at.astimezone(LOCAL_TZ) if shift.clock_out_at else None

    return {
        "id": shift.id,
        "user_username": shift.user.username,
        "user_email": shift.user.email or "",
        "user_name": shift.user.name or "",
        "clock_in_at": clock_in_local.strftime("%Y-%m-%d %H:%M:%S") if clock_in_local else None,
        "clock_out_at": clock_out_local.strftime("%Y-%m-%d %H:%M:%S") if clock_out_local else None,
        "clock_in_form": clock_in_local.strftime("%Y-%m-%dT%H:%M") if clock_in_local else "",
        "clock_out_form": clock_out_local.strftime("%Y-%m-%dT%H:%M") if clock_out_local else "",
        "clock_in_utc": shift.clock_in_at.isoformat() if shift.clock_in_at else None,
        "clock_out_utc": shift.clock_out_at.isoformat() if shift.clock_out_at else None,
        "clock_in_ip": shift.clock_in_ip,
        "clock_out_ip": shift.clock_out_ip,
        "clock_in_ua": shift.clock_in_ua,
        "clock_out_ua": shift.clock_out_ua,
        "worked_seconds": shift.worked_seconds(),
        "worked_hms": fmt_hms(shift.worked_seconds()),
        "break_count": len(shift.breaks),
        "break_seconds": shift.total_break_seconds(),
        "break_hms": fmt_hms(shift.total_break_seconds()),
        "breaks": [
            {
                "id": br.id,
                "start_at": br.start_at.isoformat() if br.start_at else None,
                "end_at": br.end_at.isoformat() if br.end_at else None,
                "is_open": br.end_at is None,
                "start_at_local": br.start_at.astimezone(LOCAL_TZ).isoformat() if br.start_at else None,
                "end_at_local": br.end_at.astimezone(LOCAL_TZ).isoformat() if br.end_at else None,
            }
            for br in sorted(shift.breaks, key=lambda br: br.start_at or shift.clock_in_at or datetime.min.replace(tzinfo=timezone.utc))
        ],
    }
