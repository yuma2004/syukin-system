import calendar
from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from ..config import LOCAL_TZ
from ..extensions import db
from ..models import Break, Shift, User
from ..services.admin_service import build_admin_overview
from ..services.audit_service import log_audit
from ..services.shift_service import get_open_break_or_abort, get_open_shift_or_abort
from ..utils.datetime_utils import fmt_date_ja, fmt_hms
from ..utils.request_meta import client_ip, user_agent
from ..utils.security import ensure_csrf, verify_csrf

bp = Blueprint("attendance", __name__)


def _greeting_for_hour(hour):
    if 5 <= hour < 11:
        return "おはようございます"
    if 11 <= hour < 18:
        return "こんにちは"
    return "お疲れさまです"


def _business_days_in_month(year, month):
    day_count = calendar.monthrange(year, month)[1]
    return sum(1 for day in range(1, day_count + 1) if datetime(year, month, day).weekday() < 5)


@bp.route("/")
@bp.route("/dashboard")
@login_required
def dashboard():
    ensure_csrf()
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(LOCAL_TZ)

    open_shift = Shift.query.filter_by(user_id=current_user.id, clock_out_at=None).order_by(Shift.id.desc()).first()
    open_break = None
    if open_shift:
        open_break = Break.query.filter_by(shift_id=open_shift.id, end_at=None).order_by(Break.id.desc()).first()

    recent = Shift.query.filter_by(user_id=current_user.id).order_by(Shift.clock_in_at.desc()).limit(10).all()
    recent_rows = []
    for shift in recent:
        clock_in_local = shift.clock_in_at.astimezone(LOCAL_TZ) if shift.clock_in_at else None
        is_current = bool(open_shift and shift.id == open_shift.id)
        if is_current and open_break:
            status_label = "休憩中"
            status_tone = "break"
        elif shift.clock_out_at:
            status_label = "退勤済み"
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
                "edit_url": url_for("admin.shift_edit", shift_id=shift.id) if current_user.is_admin() else None,
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
            Shift.user_id == current_user.id,
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
        min(100, round((month_workday_count / month_business_day_total) * 100)) if month_business_day_total else 0
    )

    month_standard_seconds = month_workday_count * 8 * 3600
    month_overtime_seconds = max(0, month_worked_seconds - month_standard_seconds)
    overtime_limit_seconds = 45 * 3600
    month_overtime_progress = (
        min(100, round((month_overtime_seconds / overtime_limit_seconds) * 100)) if overtime_limit_seconds else 0
    )

    month_stats = {
        "workday_label": f"{month_workday_count}/{month_business_day_total} 日",
        "workday_progress": month_workday_progress,
        "worked_hms": fmt_hms(month_worked_seconds),
        "overtime_hms": fmt_hms(month_overtime_seconds),
        "overtime_progress": month_overtime_progress,
    }

    admin_overview = None
    admin_snapshot = None
    if current_user.is_admin():
        try:
            admin_overview = build_admin_overview(None, None, "")
        except ValueError as exc:
            flash(str(exc), "error")

        total_users = User.query.count()
        active_now = Shift.query.filter_by(clock_out_at=None).count()
        today_start_local = datetime(now_local.year, now_local.month, now_local.day, tzinfo=LOCAL_TZ)
        tomorrow_start_local = today_start_local + timedelta(days=1)
        today_start_utc = today_start_local.astimezone(timezone.utc)
        tomorrow_start_utc = tomorrow_start_local.astimezone(timezone.utc)

        started_today = (
            db.session.query(Shift.user_id)
            .filter(Shift.clock_in_at >= today_start_utc, Shift.clock_in_at < tomorrow_start_utc)
            .distinct()
            .all()
        )
        started_today_count = len(started_today)
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
        status_text = "非勤務"
        status_tone = "idle"

    current_worked_seconds = open_shift.worked_seconds(now=now_utc) if open_shift else 0

    return render_template(
        "dashboard.html",
        greeting_text=_greeting_for_hour(now_local.hour),
        display_name=current_user.name or current_user.username,
        status_text=status_text,
        status_tone=status_tone,
        current_worked_label=fmt_hms(current_worked_seconds, precise=True),
        current_worked_seconds=current_worked_seconds,
        dashboard_now_iso=now_utc.isoformat(),
        dashboard_timezone=str(LOCAL_TZ),
        open_shift=open_shift,
        open_break=open_break,
        recent=recent,
        recent_rows=recent_rows,
        month_stats=month_stats,
        admin_overview=admin_overview,
        admin_snapshot=admin_snapshot,
    )


@bp.route("/clock/in", methods=["POST"])
@login_required
def clock_in():
    verify_csrf()
    open_shift = Shift.query.filter_by(user_id=current_user.id, clock_out_at=None).first()
    if open_shift:
        abort(400, "すでに出勤中です。先に退勤してください。")

    now = datetime.now(timezone.utc)
    shift = Shift(
        user_id=current_user.id,
        clock_in_at=now,
        clock_in_ip=client_ip(),
        clock_in_ua=user_agent(),
    )
    db.session.add(shift)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, "別の端末から既に出勤が記録されました。画面を更新して確認してください。")

    log_audit("clock_in", target_type="shift", target_id=shift.id, metadata_dict={"at": shift.clock_in_at.isoformat()})
    flash("出勤を記録しました。", "success")
    return redirect(url_for("attendance.dashboard"))


@bp.route("/clock/out", methods=["POST"])
@login_required
def clock_out():
    verify_csrf()
    shift = get_open_shift_or_abort(current_user.id)

    now = datetime.now(timezone.utc)
    open_break = Break.query.filter_by(shift_id=shift.id, end_at=None).first()
    if open_break:
        open_break.end_at = now
        open_break.end_ip = client_ip()
        open_break.end_ua = user_agent()
        db.session.add(open_break)

    shift.clock_out_at = now
    shift.clock_out_ip = client_ip()
    shift.clock_out_ua = user_agent()
    db.session.add(shift)
    db.session.commit()

    log_audit("clock_out", target_type="shift", target_id=shift.id, metadata_dict={"at": shift.clock_out_at.isoformat()})
    flash("退勤を記録しました。", "success")
    return redirect(url_for("attendance.dashboard"))


@bp.route("/break/start", methods=["POST"])
@login_required
def break_start():
    verify_csrf()
    shift = get_open_shift_or_abort(current_user.id)
    existing = Break.query.filter_by(shift_id=shift.id, end_at=None).first()
    if existing:
        abort(400, "既に休憩中です。先に休憩終了をしてください。")

    now = datetime.now(timezone.utc)
    br = Break(shift_id=shift.id, start_at=now, start_ip=client_ip(), start_ua=user_agent())
    db.session.add(br)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, "他端末から休憩開始済みです。画面を更新して再確認してください。")

    log_audit("break_start", target_type="break", target_id=br.id, metadata_dict={"at": br.start_at.isoformat(), "shift_id": shift.id})
    flash("休憩開始を記録しました。", "success")
    return redirect(url_for("attendance.dashboard"))


@bp.route("/break/end", methods=["POST"])
@login_required
def break_end():
    verify_csrf()
    shift = get_open_shift_or_abort(current_user.id)
    br = get_open_break_or_abort(shift.id)

    now = datetime.now(timezone.utc)
    br.end_at = now
    br.end_ip = client_ip()
    br.end_ua = user_agent()
    db.session.add(br)
    db.session.commit()

    log_audit("break_end", target_type="break", target_id=br.id, metadata_dict={"at": br.end_at.isoformat(), "shift_id": shift.id})
    flash("休憩終了を記録しました。", "success")
    return redirect(url_for("attendance.dashboard"))
