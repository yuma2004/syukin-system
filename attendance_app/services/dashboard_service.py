from calendar import monthrange
from datetime import datetime, timedelta, timezone

from ..config import LOCAL_TZ
from ..models import Shift, User
from ..utils.datetime_utils import fmt_date_ja, fmt_hms


def _greeting_for_hour(hour):
    if 5 <= hour < 11:
        return "おはようございます"
    if 11 <= hour < 18:
        return "こんにちは"
    return "おつかれさまです"


def _business_days_in_month(year, month):
    day_count = monthrange(year, month)[1]
    return sum(1 for day in range(1, day_count + 1) if datetime(year, month, day).weekday() < 5)


def _serialize_shift(shift):
    return {
        "id": shift.id,
        "user_id": shift.user_id,
        "clock_in_at": shift.clock_in_at.isoformat() if shift.clock_in_at else None,
        "clock_out_at": shift.clock_out_at.isoformat() if shift.clock_out_at else None,
        "clock_in_at_local": shift.clock_in_at.astimezone(LOCAL_TZ).isoformat() if shift.clock_in_at else None,
        "clock_out_at_local": shift.clock_out_at.astimezone(LOCAL_TZ).isoformat() if shift.clock_out_at else None,
        "is_open": shift.clock_out_at is None,
        "worked_seconds": shift.worked_seconds(),
        "worked_hms": fmt_hms(shift.worked_seconds()),
        "break_seconds": shift.total_break_seconds(),
        "break_hms": fmt_hms(shift.total_break_seconds()),
        "break_count": len(shift.breaks),
        "clock_in_ip": shift.clock_in_ip,
        "clock_in_ua": shift.clock_in_ua,
        "clock_out_ip": shift.clock_out_ip,
        "clock_out_ua": shift.clock_out_ua,
    }


def build_dashboard_context(user):
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(LOCAL_TZ)

    open_shift = Shift.query.filter_by(user_id=user.id, clock_out_at=None).order_by(Shift.id.desc()).first()
    open_break = None
    if open_shift:
        open_break = next((br for br in open_shift.breaks if br.end_at is None), None)

    recent = Shift.query.filter_by(user_id=user.id).order_by(Shift.clock_in_at.desc()).limit(10).all()
    recent_rows = []
    for shift in recent:
        clock_in_local = shift.clock_in_at.astimezone(LOCAL_TZ) if shift.clock_in_at else None
        is_current = bool(open_shift and shift.id == open_shift.id)
        if is_current and open_break:
            status_label = "休憩中"
            status_tone = "break"
        elif shift.clock_out_at:
            status_label = "終了"
            status_tone = "done"
        else:
            status_label = "勤務中"
            status_tone = "active"

        recent_rows.append(
            {
                "id": shift.id,
                "date_label": fmt_date_ja(clock_in_local) if clock_in_local else "-",
                "time_label": clock_in_local.strftime("%H:%M") if clock_in_local else "-",
                "status_label": status_label,
                "status_tone": status_tone,
                "worked_label": fmt_hms(shift.worked_seconds(now=now_utc), precise=True),
                "break_label": fmt_hms(shift.total_break_seconds(now=now_utc), precise=True),
            }
        )

    month_start_local = datetime(now_local.year, now_local.month, 1, tzinfo=LOCAL_TZ)
    if now_local.month == 12:
        next_month_local = datetime(now_local.year + 1, 1, 1, tzinfo=LOCAL_TZ)
    else:
        next_month_local = datetime(now_local.year, now_local.month + 1, 1, tzinfo=LOCAL_TZ)
    month_end_local = next_month_local - timedelta(microseconds=1)
    month_start_utc = month_start_local.astimezone(timezone.utc)
    month_end_utc = month_end_local.astimezone(timezone.utc)

    month_shifts = (
        Shift.query.filter(
            Shift.user_id == user.id,
            Shift.clock_in_at >= month_start_utc,
            Shift.clock_in_at <= month_end_utc,
        )
        .order_by(Shift.clock_in_at.desc())
        .all()
    )

    month_workdays = set()
    month_worked_seconds = 0
    for shift in month_shifts:
        if shift.clock_in_at:
            month_workdays.add(shift.clock_in_at.astimezone(LOCAL_TZ).date())
        month_worked_seconds += shift.worked_seconds(now=now_utc)

    month_workday_count = len(month_workdays)
    month_business_day_total = _business_days_in_month(now_local.year, now_local.month)
    month_workday_progress = (
        min(100, round((month_workday_count / month_business_day_total) * 100))
        if month_business_day_total
        else 0
    )

    month_standard_seconds = month_workday_count * 8 * 3600
    month_overtime_seconds = max(0, month_worked_seconds - month_standard_seconds)
    overtime_limit_seconds = 45 * 3600
    month_overtime_progress = (
        min(100, round((month_overtime_seconds / overtime_limit_seconds) * 100))
        if overtime_limit_seconds
        else 0
    )

    month_stats = {
        "workday_label": f"{month_workday_count}/{month_business_day_total}日",
        "workday_progress": month_workday_progress,
        "worked_hms": fmt_hms(month_worked_seconds),
        "overtime_hms": fmt_hms(month_overtime_seconds),
        "overtime_progress": month_overtime_progress,
    }

    # Keep this behavior consistent with the old dashboard:
    # admin-only snapshot for dashboard cards (same data is reused by admin UI too).
    admin_snapshot = None
    if user.is_admin():
        total_users = User.query.count()
        active_now = Shift.query.filter_by(clock_out_at=None).count()

        today_start_local = datetime(now_local.year, now_local.month, now_local.day, tzinfo=LOCAL_TZ)
        tomorrow_start_local = today_start_local + timedelta(days=1)
        today_start_utc = today_start_local.astimezone(timezone.utc)
        tomorrow_start_utc = tomorrow_start_local.astimezone(timezone.utc)

        started_today_count = (
            Shift.query.with_entities(Shift.user_id)
            .filter(Shift.clock_in_at >= today_start_utc, Shift.clock_in_at < tomorrow_start_utc)
            .distinct()
            .count()
        )

        admin_snapshot = {
            "active_now": active_now,
            "not_clocked_in_today": max(0, total_users - started_today_count),
        }

    if open_shift and open_break:
        status_text = "休憩中"
        status_tone = "break"
    elif open_shift:
        status_text = "勤務中"
        status_tone = "active"
    else:
        status_text = "未勤務"
        status_tone = "idle"

    current_worked_seconds = open_shift.worked_seconds(now=now_utc) if open_shift else 0

    return {
        "greeting_text": _greeting_for_hour(now_local.hour),
        "display_name": user.name or user.username,
        "status_text": status_text,
        "status_tone": status_tone,
        "current_worked_label": fmt_hms(current_worked_seconds, precise=True),
        "current_worked_seconds": current_worked_seconds,
        "dashboard_now_iso": now_utc.isoformat(),
        "dashboard_timezone": str(LOCAL_TZ),
        "open_shift": open_shift,
        "open_break": open_break,
        "recent": recent,
        "recent_rows": recent_rows,
        "month_stats": month_stats,
        "admin_snapshot": admin_snapshot,
    }


def _serialize_break(break_row):
    return {
        "id": break_row.id,
        "start_at": break_row.start_at.isoformat() if break_row.start_at else None,
        "end_at": break_row.end_at.isoformat() if break_row.end_at else None,
        "start_at_local": break_row.start_at.astimezone(LOCAL_TZ).isoformat() if break_row.start_at else None,
        "end_at_local": break_row.end_at.astimezone(LOCAL_TZ).isoformat() if break_row.end_at else None,
        "start_ip": break_row.start_ip,
        "start_ua": break_row.start_ua,
        "end_ip": break_row.end_ip,
        "end_ua": break_row.end_ua,
        "is_open": break_row.end_at is None,
    }


def build_dashboard_payload(user):
    context = build_dashboard_context(user)
    return {
        **{
            key: value
            for key, value in context.items()
            if key not in {"open_shift", "open_break", "recent", "recent_rows"}
        },
        "open_shift": _serialize_shift(context["open_shift"]) if context["open_shift"] else None,
        "open_break": _serialize_break(context["open_break"]) if context["open_break"] else None,
        "recent": [
            {
                "id": shift.id,
                "clock_in_at": shift.clock_in_at.isoformat() if shift.clock_in_at else None,
                "clock_out_at": shift.clock_out_at.isoformat() if shift.clock_out_at else None,
                "worked_seconds": shift.worked_seconds(),
                "worked_hms": fmt_hms(shift.worked_seconds()),
            }
            for shift in context["recent"]
        ],
        "recent_rows": context["recent_rows"],
    }
