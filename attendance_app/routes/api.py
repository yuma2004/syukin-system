from datetime import datetime, timedelta, timezone
import json

from flask import Blueprint, abort, jsonify, request, session
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from ..authz import require_admin
from ..config import LOCAL_TZ
from ..extensions import db
from ..models import AuditLog, Break, Shift, User
from ..services.admin_service import build_shift_detail_payload
from ..services.audit_service import log_audit
from ..services.dashboard_service import build_dashboard_payload
from ..services.shift_query_service import apply_shift_user_filters, build_shift_range_query
from ..utils.datetime_utils import fmt_hms, parse_local_datetime
from ..utils.request_meta import client_ip, user_agent
from ..utils.security import ensure_csrf

bp = Blueprint("api", __name__, url_prefix="/api")


def _ok(data=None, status=200):
    payload = {"ok": True}
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status


def _error(message, status=400):
    return jsonify({"ok": False, "error": {"message": str(message)}}), status


def _request_payload():
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        return payload
    return request.form.to_dict()


def _serialize_user(user):
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_admin": user.is_admin(),
    }


def _parse_time(value, label):
    try:
        return parse_local_datetime(value, label)
    except ValueError as exc:
        abort(400, str(exc))


def _serialize_break_row(break_row):
    return {
        "id": break_row.id,
        "start_at": break_row.start_at.isoformat() if break_row.start_at else None,
        "end_at": break_row.end_at.isoformat() if break_row.end_at else None,
        "start_at_local": break_row.start_at.astimezone(LOCAL_TZ).isoformat() if break_row.start_at else None,
        "end_at_local": break_row.end_at.astimezone(LOCAL_TZ).isoformat() if break_row.end_at else None,
        "is_open": break_row.end_at is None,
        "start_ip": break_row.start_ip,
        "start_ua": break_row.start_ua,
        "end_ip": break_row.end_ip,
        "end_ua": break_row.end_ua,
    }


def _serialize_shift(shift):
    clocked_seconds = shift.worked_seconds()
    break_seconds = shift.total_break_seconds()
    return {
        "id": shift.id,
        "user": _serialize_user(shift.user),
        "clock_in_at": shift.clock_in_at.isoformat() if shift.clock_in_at else None,
        "clock_out_at": shift.clock_out_at.isoformat() if shift.clock_out_at else None,
        "clock_in_at_local": shift.clock_in_at.astimezone(LOCAL_TZ).isoformat() if shift.clock_in_at else None,
        "clock_out_at_local": shift.clock_out_at.astimezone(LOCAL_TZ).isoformat() if shift.clock_out_at else None,
        "clock_in_ip": shift.clock_in_ip,
        "clock_in_ua": shift.clock_in_ua,
        "clock_out_ip": shift.clock_out_ip,
        "clock_out_ua": shift.clock_out_ua,
        "worked_seconds": clocked_seconds,
        "worked_hms": fmt_hms(max(0, int(clocked_seconds))),
        "break_seconds": break_seconds,
        "break_hms": fmt_hms(max(0, int(break_seconds))),
        "break_count": len(shift.breaks),
        "breaks": [_serialize_break_row(br) for br in sorted(shift.breaks, key=lambda row: row.start_at or datetime.min.replace(tzinfo=timezone.utc))],
        "is_open": shift.clock_out_at is None,
    }


def _serialize_audit(log):
    try:
        metadata = json.loads(log.metadata_json) if log.metadata_json else {}
    except Exception:
        metadata = {"raw": log.metadata_json}

    return {
        "id": log.id,
        "created_at": log.created_at.isoformat() if log.created_at else None,
        "created_at_local": log.created_at.astimezone(LOCAL_TZ).isoformat() if log.created_at else None,
        "action": log.action,
        "user_id": log.user_id,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "ip": log.ip,
        "user_agent": log.user_agent,
        "metadata": metadata,
        "signature": log.signature,
    }


@bp.errorhandler(HTTPException)
def _api_error_handler(error):
    return _error(getattr(error, "description", str(error)), status=error.code or 500)


@bp.get("/session")
def session_status():
    ensure_csrf()
    return _ok(
        {
            "authenticated": current_user.is_authenticated,
            "is_admin": current_user.is_authenticated and current_user.is_admin(),
            "user": _serialize_user(current_user) if current_user.is_authenticated else None,
            "timezone": str(LOCAL_TZ),
            "csrf_token": session.get("csrf_token"),
        }
    )


@bp.post("/login")
def api_login():
    ensure_csrf()
    payload = _request_payload()
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    remember_me = str(payload.get("remember_me", "")).lower() in {"1", "true", "on", "yes"}

    if not username or not password:
        return _error("username and password are required", 400)

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return _error("invalid credentials", 401)

    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()
    login_user(user, remember=remember_me)
    log_audit("login", target_type="user", target_id=user.id, metadata_dict={"username": username})
    return _ok(_serialize_user(user))


@bp.post("/logout")
@login_required
def api_logout():
    log_audit("logout", target_type="user", target_id=current_user.id)
    logout_user()
    return _ok({"authenticated": False})


@bp.get("/dashboard")
@login_required
def api_dashboard():
    payload = build_dashboard_payload(current_user)
    payload["user"] = _serialize_user(current_user)
    return _ok(payload)


@bp.post("/clock/in")
@login_required
def api_clock_in():
    if Shift.query.filter_by(user_id=current_user.id, clock_out_at=None).first():
        return _error("already clocked in", 400)
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
        return _error("cannot clock in", 400)
    log_audit("clock_in", target_type="shift", target_id=shift.id, metadata_dict={"at": shift.clock_in_at.isoformat()})
    return _ok(build_dashboard_payload(current_user))


@bp.post("/clock/out")
@login_required
def api_clock_out():
    shift = Shift.query.filter_by(user_id=current_user.id, clock_out_at=None).first()
    if not shift:
        return _error("no open shift", 400)

    now = datetime.now(timezone.utc)
    break_row = Break.query.filter_by(shift_id=shift.id, end_at=None).first()
    if break_row:
        break_row.end_at = now
        break_row.end_ip = client_ip()
        break_row.end_ua = user_agent()
        db.session.add(break_row)
    shift.clock_out_at = now
    shift.clock_out_ip = client_ip()
    shift.clock_out_ua = user_agent()
    db.session.add(shift)
    db.session.commit()
    log_audit("clock_out", target_type="shift", target_id=shift.id, metadata_dict={"at": shift.clock_out_at.isoformat()})
    return _ok(build_dashboard_payload(current_user))


@bp.post("/break/start")
@login_required
def api_break_start():
    shift = Shift.query.filter_by(user_id=current_user.id, clock_out_at=None).first()
    if not shift:
        return _error("no open shift", 400)
    if Break.query.filter_by(shift_id=shift.id, end_at=None).first():
        return _error("already on break", 400)

    now = datetime.now(timezone.utc)
    br = Break(
        shift_id=shift.id,
        start_at=now,
        start_ip=client_ip(),
        start_ua=user_agent(),
    )
    db.session.add(br)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("cannot start break", 400)
    log_audit("break_start", target_type="break", target_id=br.id, metadata_dict={"shift_id": shift.id, "at": br.start_at.isoformat()})
    return _ok(build_dashboard_payload(current_user))


@bp.post("/break/end")
@login_required
def api_break_end():
    shift = Shift.query.filter_by(user_id=current_user.id, clock_out_at=None).first()
    if not shift:
        return _error("no open shift", 400)
    br = Break.query.filter_by(shift_id=shift.id, end_at=None).first()
    if not br:
        return _error("no open break", 400)
    br.end_at = datetime.now(timezone.utc)
    br.end_ip = client_ip()
    br.end_ua = user_agent()
    db.session.commit()
    log_audit("break_end", target_type="break", target_id=br.id, metadata_dict={"shift_id": shift.id, "at": br.end_at.isoformat()})
    return _ok(build_dashboard_payload(current_user))


@bp.get("/admin/shifts")
@login_required
def api_admin_shifts():
    require_admin()
    start_arg = request.args.get("start")
    end_arg = request.args.get("end")
    user_username = request.args.get("username", "").strip()
    user_email = request.args.get("email", "").strip().lower()

    if start_arg or end_arg:
        try:
            start_date = datetime.fromisoformat(start_arg).date() if start_arg else None
            end_date = datetime.fromisoformat(end_arg).date() if end_arg else None
        except ValueError as exc:
            return _error(str(exc), 400)
        if not start_date or not end_date:
            return _error("both start and end are required when filtering", 400)
    else:
        now_local = datetime.now(LOCAL_TZ).date()
        start_date = now_local - timedelta(days=13)
        end_date = now_local

    query, start_date, end_date = build_shift_range_query(start_date, end_date)
    query = apply_shift_user_filters(query, user_username=user_username or None, user_email=user_email or None)
    shifts = query.order_by(Shift.clock_in_at.desc()).all()

    return _ok(
        {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "items": [_serialize_shift(shift) for shift in shifts],
            "user_username": user_username or "",
            "user_email": user_email or "",
        }
    )


@bp.post("/admin/shifts")
@login_required
def api_admin_create_shift():
    require_admin()
    payload = _request_payload()
    user_id = payload.get("user_id")
    if not user_id:
        return _error("user_id is required", 400)

    user = User.query.get(user_id)
    if not user:
        return _error("user not found", 404)

    clock_in_at = _parse_time(payload.get("clock_in_at"), "clock_in_at")
    clock_out_at = _parse_time(payload.get("clock_out_at"), "clock_out_at")
    if clock_out_at and clock_out_at < clock_in_at:
        return _error("clock_out_at must be later than clock_in_at", 400)

    shift = Shift(user_id=user.id, clock_in_at=clock_in_at, clock_out_at=clock_out_at)
    db.session.add(shift)
    db.session.commit()
    log_audit("admin_shift_create", target_type="shift", target_id=shift.id, metadata_dict={"user_id": user.id})
    return _ok(_serialize_shift(shift), 201)


@bp.get("/admin/shifts/<int:shift_id>")
@login_required
def api_admin_shift_detail(shift_id):
    require_admin()
    shift = Shift.query.get_or_404(shift_id)
    return _ok(build_shift_detail_payload(shift))


@bp.patch("/admin/shifts/<int:shift_id>")
@login_required
def api_admin_shift_update(shift_id):
    require_admin()
    shift = Shift.query.get_or_404(shift_id)
    payload = _request_payload()
    clock_in_at = _parse_time(payload.get("clock_in_at"), "clock_in_at")
    clock_out_at = _parse_time(payload.get("clock_out_at"), "clock_out_at")
    if not clock_in_at:
        return _error("clock_in_at is required", 400)
    if clock_out_at and clock_out_at < clock_in_at:
        return _error("clock_out_at must be later than clock_in_at", 400)

    old = {"clock_in_at": shift.clock_in_at.isoformat() if shift.clock_in_at else None, "clock_out_at": shift.clock_out_at.isoformat() if shift.clock_out_at else None}
    shift.clock_in_at = clock_in_at
    shift.clock_out_at = clock_out_at
    db.session.commit()
    log_audit(
        "admin_shift_update",
        target_type="shift",
        target_id=shift.id,
        metadata_dict={"old": old, "new": {"clock_in_at": shift.clock_in_at.isoformat(), "clock_out_at": shift.clock_out_at.isoformat() if shift.clock_out_at else None}},
    )
    return _ok(_serialize_shift(shift))


@bp.delete("/admin/shifts/<int:shift_id>")
@login_required
def api_admin_shift_delete(shift_id):
    require_admin()
    shift = Shift.query.get_or_404(shift_id)
    db.session.delete(shift)
    db.session.commit()
    log_audit("admin_shift_delete", target_type="shift", target_id=shift_id)
    return _ok({"deleted": shift_id})


@bp.post("/admin/shifts/<int:shift_id>/breaks")
@login_required
def api_admin_shift_break_add(shift_id):
    require_admin()
    shift = Shift.query.get_or_404(shift_id)
    payload = _request_payload()
    start_at = _parse_time(payload.get("start_at"), "start_at")
    end_at = _parse_time(payload.get("end_at"), "end_at")
    if end_at and end_at < start_at:
        return _error("end_at must be later than start_at", 400)

    br = Break(shift_id=shift.id, start_at=start_at, end_at=end_at)
    db.session.add(br)
    db.session.commit()
    log_audit("admin_break_add", target_type="break", target_id=br.id, metadata_dict={"shift_id": shift.id})
    return _ok(_serialize_break_row(br), 201)


@bp.patch("/admin/shifts/<int:shift_id>/breaks/<int:break_id>")
@login_required
def api_admin_break_update(shift_id, break_id):
    require_admin()
    shift = Shift.query.get_or_404(shift_id)
    break_row = Break.query.filter_by(id=break_id, shift_id=shift.id).first_or_404()
    payload = _request_payload()
    start_at = _parse_time(payload.get("start_at"), "start_at")
    end_at = _parse_time(payload.get("end_at"), "end_at")
    if end_at and end_at < start_at:
        return _error("end_at must be later than start_at", 400)

    break_row.start_at = start_at
    break_row.end_at = end_at
    db.session.commit()
    return _ok(_serialize_break_row(break_row))


@bp.delete("/admin/shifts/<int:shift_id>/breaks/<int:break_id>")
@login_required
def api_admin_break_delete(shift_id, break_id):
    require_admin()
    shift = Shift.query.get_or_404(shift_id)
    break_row = Break.query.filter_by(id=break_id, shift_id=shift.id).first_or_404()
    db.session.delete(break_row)
    db.session.commit()
    return _ok({"deleted": break_id})


@bp.post("/admin/shifts/<int:shift_id>/breaks/reset")
@login_required
def api_admin_break_reset(shift_id):
    require_admin()
    shift = Shift.query.get_or_404(shift_id)
    deleted = len(shift.breaks)
    for break_row in list(shift.breaks):
        db.session.delete(break_row)
    db.session.commit()
    log_audit("admin_break_reset", target_type="shift", target_id=shift.id, metadata_dict={"count": deleted})
    return _ok({"deleted": deleted})


@bp.get("/admin/users")
@login_required
def api_admin_users():
    require_admin()
    search = request.args.get("search", "").strip()
    role = request.args.get("role", "").strip()
    query = User.query
    if role:
        query = query.filter(User.role == role)
    if search:
        search_like = f"%{search}%"
        query = query.filter(
            (User.username.ilike(search_like))
            | (User.email.ilike(search_like))
            | (User.name.ilike(search_like))
        )
    users = query.order_by(User.username.asc()).all()
    return _ok({"items": [_serialize_user(user) for user in users]})


@bp.post("/admin/users")
@login_required
def api_admin_user_create():
    require_admin()
    payload = _request_payload()
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    name = str(payload.get("name", "")).strip() or None
    email = str(payload.get("email", "")).strip() or None
    role = str(payload.get("role", "user")).strip() or "user"

    if not username or not password:
        return _error("username and password are required", 400)
    if User.query.filter_by(username=username).first():
        return _error("username already exists", 409)
    if email and User.query.filter_by(email=email).first():
        return _error("email already exists", 409)

    user = User(username=username, name=name, email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    log_audit("admin_user_create", target_type="user", target_id=user.id, metadata_dict={"username": username, "role": role})
    return _ok(_serialize_user(user), 201)


@bp.patch("/admin/users/<int:user_id>")
@login_required
def api_admin_user_update(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    payload = _request_payload()

    username = str(payload.get("username", "")).strip()
    if username and username != user.username:
        if User.query.filter(User.username == username, User.id != user.id).first():
            return _error("username already exists", 409)
        user.username = username

    user.name = str(payload.get("name", "")).strip() or user.name
    email = str(payload.get("email", "")).strip()
    if email:
        if email != user.email and User.query.filter(User.email == email, User.id != user.id).first():
            return _error("email already exists", 409)
        user.email = email
    elif "email" in payload:
        user.email = None

    user.role = str(payload.get("role", user.role)).strip() or user.role

    password = str(payload.get("password", "")).strip()
    if password:
        user.set_password(password)

    db.session.commit()
    log_audit("admin_user_update", target_type="user", target_id=user.id, metadata_dict={"username": user.username})
    return _ok(_serialize_user(user))


@bp.delete("/admin/users/<int:user_id>")
@login_required
def api_admin_user_delete(user_id):
    require_admin()
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return _error("cannot delete own account", 400)
    db.session.delete(user)
    db.session.commit()
    log_audit("admin_user_delete", target_type="user", target_id=user_id)
    return _ok({"deleted": user_id})


@bp.get("/admin/audit")
@login_required
def api_admin_audit():
    require_admin()
    action = request.args.get("action", "").strip()
    username = request.args.get("username", "").strip()
    try:
        limit = int(request.args.get("limit", "200"))
    except ValueError:
        limit = 200
    limit = max(1, min(limit, 5000))

    action_choices = [
        row[0]
        for row in AuditLog.query.with_entities(AuditLog.action)
        .distinct()
        .order_by(AuditLog.action.asc())
        .all()
    ]
    query = AuditLog.query.order_by(AuditLog.created_at.desc())
    if action:
        query = query.filter(AuditLog.action == action)
    if username:
        query = query.join(User).filter(User.username == username)
    logs = query.limit(limit).all()

    return _ok({"items": [_serialize_audit(log) for log in logs], "action_choices": action_choices})
