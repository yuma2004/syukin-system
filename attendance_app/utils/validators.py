from ..config import CSV_EXPORT_MAX_DAYS


def ensure_valid_range(start_date, end_date):
    if start_date > end_date:
        raise ValueError("終了日は開始日以降を指定してください。")

    span_days = (end_date - start_date).days + 1
    if span_days > CSV_EXPORT_MAX_DAYS:
        raise ValueError(f"期間は最大{CSV_EXPORT_MAX_DAYS}日までにしてください。")

    return start_date, end_date
