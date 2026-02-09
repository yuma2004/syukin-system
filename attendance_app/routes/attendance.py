from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Break, Shift
from ..services.admin_service import build_admin_overview
from ..services.audit_service import log_audit
from ..services.shift_service import get_open_break_or_abort, get_open_shift_or_abort
from ..utils.request_meta import client_ip, user_agent
from ..utils.security import ensure_csrf, verify_csrf

bp = Blueprint("attendance", __name__)


@bp.route("/")
@bp.route("/dashboard")
@login_required
def dashboard():
    ensure_csrf()
    open_shift = Shift.query.filter_by(user_id=current_user.id, clock_out_at=None).order_by(Shift.id.desc()).first()
    open_break = None
    if open_shift:
        open_break = Break.query.filter_by(shift_id=open_shift.id, end_at=None).order_by(Break.id.desc()).first()

    recent = Shift.query.filter_by(user_id=current_user.id).order_by(Shift.clock_in_at.desc()).limit(10).all()

    admin_overview = None
    if current_user.is_admin():
        try:
            admin_overview = build_admin_overview(None, None, "")
        except ValueError as exc:
            flash(str(exc), "error")

    return render_template(
        "dashboard.html",
        open_shift=open_shift,
        open_break=open_break,
        recent=recent,
        admin_overview=admin_overview,
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
