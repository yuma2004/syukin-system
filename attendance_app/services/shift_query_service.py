from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import selectinload

from ..config import LOCAL_TZ
from ..models import Shift, User
from ..utils.validators import ensure_valid_range


def build_shift_range_query(start_date, end_date):
    start_date, end_date = ensure_valid_range(start_date, end_date)
    start_utc = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    end_utc = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)

    query = (
        Shift.query.options(selectinload(Shift.user), selectinload(Shift.breaks))
        .join(User)
        .filter(Shift.clock_in_at >= start_utc, Shift.clock_in_at <= end_utc)
    )
    return query, start_date, end_date


def apply_shift_user_filters(query, user_username=None, user_email=None):
    if user_username:
        return query.filter(User.username == user_username)
    if user_email:
        return query.filter(func.lower(User.email) == user_email)
    return query
