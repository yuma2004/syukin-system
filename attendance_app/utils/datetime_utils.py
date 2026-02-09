from datetime import datetime, timezone

from ..config import LOCAL_TZ, WEEKDAY_JA


def ensure_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def parse_local_datetime(value, field_label="日時"):
    if value is None:
        return None

    value = value.strip()
    if not value:
        return None

    formats = ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S")
    last_error = None
    for fmt in formats:
        try:
            local_dt = datetime.strptime(value, fmt)
            return local_dt.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
        except ValueError as exc:
            last_error = exc

    raise ValueError(f"{field_label}の形式が不正です: {value}") from last_error


def format_local_form_value(dt):
    aware = ensure_aware(dt)
    if not aware:
        return ""
    return aware.astimezone(LOCAL_TZ).strftime("%Y-%m-%dT%H:%M")


def fmt_dt(dt, full=False):
    if not dt:
        return "-"

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    local = dt.astimezone(LOCAL_TZ)
    weekday = WEEKDAY_JA[local.weekday()]
    if full:
        return (
            f"{local.year}年{local.month:02d}月{local.day:02d}日({weekday}) "
            f"{local.hour:02d}:{local.minute:02d}:{local.second:02d}"
        )
    return f"{local.month:02d}月{local.day:02d}日({weekday}) {local.hour:02d}:{local.minute:02d}"


def fmt_hms(seconds, precise=False):
    seconds = int(seconds or 0)
    hour = seconds // 3600
    minute = (seconds % 3600) // 60
    sec = seconds % 60

    if precise:
        return f"{hour:02d}:{minute:02d}:{sec:02d}"
    return f"{hour:02d}:{minute:02d}"


def fmt_date_ja(value, full=False):
    if not value:
        return "-"

    if isinstance(value, datetime):
        value = ensure_aware(value).astimezone(LOCAL_TZ).date()
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            value = ensure_aware(parsed).astimezone(LOCAL_TZ).date()
        except ValueError:
            return value

    weekday = WEEKDAY_JA[value.weekday()]
    if full:
        return f"{value.year}年{value.month:02d}月{value.day:02d}日({weekday})"
    return f"{value.month:02d}月{value.day:02d}日({weekday})"
