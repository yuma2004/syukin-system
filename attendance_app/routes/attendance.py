from datetime import datetime, timezone

from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Break, Shift
from ..services.dashboard_service import build_dashboard_context
from ..services.audit_service import log_audit
from ..services.shift_service import (
    OpenBreakNotFoundError,
    OpenShiftNotFoundError,
    get_open_break_or_abort,
    get_open_shift_or_abort,
)
from ..utils.request_meta import client_ip, user_agent
from ..utils.security import ensure_csrf, verify_csrf

bp = Blueprint("attendance", __name__)

_OPEN_SHIFT_REQUIRED_MESSAGE = "勤務中のシフトがありません"
_OPEN_BREAK_REQUIRED_MESSAGE = "開始中の休憩がありません"


def _serve_react_if_enabled():
    if current_app.config.get("REACT_UI_ENABLED"):
        return current_app.send_static_file("spa/index.html")
    return None


@bp.route("/")
@bp.route("/dashboard")
@login_required
def dashboard():
    ensure_csrf()
    react_response = _serve_react_if_enabled()
    if react_response:
        return react_response
    return render_template("dashboard.html", **build_dashboard_context(current_user))


@bp.route("/clock/in", methods=["POST"])
@login_required
def clock_in():
    verify_csrf()
    open_shift = Shift.query.filter_by(user_id=current_user.id, clock_out_at=None).first()
    if open_shift:
        flash("まだ勤務中のシフトがあります", "error")
        return redirect(url_for("attendance.dashboard"), code=400)

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
        flash("既存の開いているシフトと競合したため開始できません", "error")
        return redirect(url_for("attendance.dashboard"))

    log_audit("clock_in", target_type="shift", target_id=shift.id, metadata_dict={"at": shift.clock_in_at.isoformat()})
    flash("出勤しました", "success")
    return redirect(url_for("attendance.dashboard"))


@bp.route("/clock/out", methods=["POST"])
@login_required
def clock_out():
    verify_csrf()
    try:
        shift = get_open_shift_or_abort(current_user.id)
    except OpenShiftNotFoundError:
        flash(_OPEN_SHIFT_REQUIRED_MESSAGE, "error")
        return redirect(url_for("attendance.dashboard"), code=400)

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
    flash("退勤しました", "success")
    return redirect(url_for("attendance.dashboard"))


@bp.route("/break/start", methods=["POST"])
@login_required
def break_start():
    verify_csrf()
    try:
        shift = get_open_shift_or_abort(current_user.id)
    except OpenShiftNotFoundError:
        flash(_OPEN_SHIFT_REQUIRED_MESSAGE, "error")
        return redirect(url_for("attendance.dashboard"), code=400)

    existing = Break.query.filter_by(shift_id=shift.id, end_at=None).first()
    if existing:
        flash("すでに休憩中です", "error")
        return redirect(url_for("attendance.dashboard"), code=400)

    now = datetime.now(timezone.utc)
    br = Break(shift_id=shift.id, start_at=now, start_ip=client_ip(), start_ua=user_agent())
    db.session.add(br)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("既存の休憩と競合し、開始できませんでした", "error")
        return redirect(url_for("attendance.dashboard"), code=400)

    log_audit(
        "break_start",
        target_type="break",
        target_id=br.id,
        metadata_dict={"at": br.start_at.isoformat(), "shift_id": shift.id},
    )
    flash("休憩を開始しました", "success")
    return redirect(url_for("attendance.dashboard"))


@bp.route("/break/end", methods=["POST"])
@login_required
def break_end():
    verify_csrf()
    try:
        shift = get_open_shift_or_abort(current_user.id)
    except OpenShiftNotFoundError:
        flash(_OPEN_SHIFT_REQUIRED_MESSAGE, "error")
        return redirect(url_for("attendance.dashboard"), code=400)

    try:
        br = get_open_break_or_abort(shift.id)
    except OpenBreakNotFoundError:
        flash(_OPEN_BREAK_REQUIRED_MESSAGE, "error")
        return redirect(url_for("attendance.dashboard"), code=400)

    now = datetime.now(timezone.utc)
    br.end_at = now
    br.end_ip = client_ip()
    br.end_ua = user_agent()
    db.session.add(br)
    db.session.commit()

    log_audit(
        "break_end",
        target_type="break",
        target_id=br.id,
        metadata_dict={"at": br.end_at.isoformat(), "shift_id": shift.id},
    )
    flash("休憩を終了しました", "success")
    return redirect(url_for("attendance.dashboard"))
