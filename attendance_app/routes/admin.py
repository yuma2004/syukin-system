from datetime import datetime, timedelta

from flask import Blueprint, abort, current_app, flash, jsonify, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from ..authz import require_admin
from ..config import LOCAL_TZ
from ..extensions import db
from ..models import AuditLog, Break, Shift, User
from ..services.admin_service import build_admin_overview, build_shift_detail_payload, build_shift_edit_context
from ..services.audit_service import log_audit
from ..services.csv_service import generate_attendance_csv
from ..utils.datetime_utils import parse_local_datetime
from ..utils.request_meta import client_ip, user_agent
from ..utils.security import ensure_csrf, verify_csrf
from ..utils.validators import ensure_valid_range

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _serve_react_if_enabled():
    if current_app.config.get("REACT_UI_ENABLED"):
        return current_app.send_static_file("spa/index.html")
    return None


def _admin_redirect_with_filters():
    params = {}
    for key in ("start", "end", "username"):
        value = request.form.get(key, "").strip()
        if value:
            params[key] = value
    return redirect(url_for("admin.dashboard", **params))


def _parse_shift_datetimes(form):
    clock_in_at = parse_local_datetime(form.get("clock_in_at"), "出勤")
    if not clock_in_at:
        raise ValueError("出勤時刻は必須です")

    clock_out_at = parse_local_datetime(form.get("clock_out_at"), "退勤")
    if clock_out_at and clock_out_at < clock_in_at:
        raise ValueError("退勤時刻は出勤時刻より後にしてください")

    return clock_in_at, clock_out_at


def _parse_break_datetimes(form):
    start_at = parse_local_datetime(form.get("start_at"), "休憩開始")
    end_at = parse_local_datetime(form.get("end_at"), "休憩終了")
    if not start_at:
        raise ValueError("休憩開始時刻は必須です")
    if end_at and end_at < start_at:
        raise ValueError("休憩終了時刻は開始時刻より後にしてください")
    return start_at, end_at


def _find_shift_break_or_404(shift_id):
    break_id = int(request.form.get("break_id", "0"))
    target_break = Break.query.filter_by(id=break_id, shift_id=shift_id).first()
    if not target_break:
        abort(404, "休憩記録が見つかりません")
    return target_break, break_id


def _handle_shift_update_action(shift, shift_id):
    old_values = {
        "clock_in_at": shift.clock_in_at.isoformat() if shift.clock_in_at else None,
        "clock_out_at": shift.clock_out_at.isoformat() if shift.clock_out_at else None,
    }

    clock_in_at, clock_out_at = _parse_shift_datetimes(request.form)
    shift.clock_in_at = clock_in_at
    shift.clock_out_at = clock_out_at
    db.session.commit()

    new_values = {
        "clock_in_at": shift.clock_in_at.isoformat() if shift.clock_in_at else None,
        "clock_out_at": shift.clock_out_at.isoformat() if shift.clock_out_at else None,
    }

    log_audit(
        "admin_shift_edit",
        target_type="shift",
        target_id=shift_id,
        metadata_dict={
            "user_username": shift.user.username,
            "user_email": shift.user.email or "",
            "old_values": old_values,
            "new_values": new_values,
        },
    )
    flash("勤務記録を更新しました", "success")
    return redirect(url_for("admin.dashboard"))


def _handle_break_add_action(shift, shift_id):
    start_at, end_at = _parse_break_datetimes(request.form)

    new_break = Break(shift_id=shift.id, start_at=start_at, end_at=end_at)
    db.session.add(new_break)
    db.session.commit()

    log_audit(
        "admin_break_add",
        target_type="break",
        target_id=new_break.id,
        metadata_dict={
            "shift_id": shift.id,
            "start_at": new_break.start_at.isoformat() if new_break.start_at else None,
            "end_at": new_break.end_at.isoformat() if new_break.end_at else None,
        },
    )
    flash("休憩を追加しました", "success")
    return redirect(url_for("admin.shift_edit", shift_id=shift_id))


def _handle_break_update_action(shift, shift_id):
    target_break, _ = _find_shift_break_or_404(shift_id)
    old_values = {
        "start_at": target_break.start_at.isoformat() if target_break.start_at else None,
        "end_at": target_break.end_at.isoformat() if target_break.end_at else None,
    }

    start_at, end_at = _parse_break_datetimes(request.form)
    target_break.start_at = start_at
    target_break.end_at = end_at
    db.session.commit()

    new_values = {
        "start_at": target_break.start_at.isoformat() if target_break.start_at else None,
        "end_at": target_break.end_at.isoformat() if target_break.end_at else None,
    }

    log_audit(
        "admin_break_update",
        target_type="break",
        target_id=target_break.id,
        metadata_dict={
            "shift_id": shift.id,
            "old_values": old_values,
            "new_values": new_values,
        },
    )
    flash("休憩を更新しました", "success")
    return redirect(url_for("admin.shift_edit", shift_id=shift_id))


def _handle_break_delete_action(shift, shift_id):
    target_break, break_id = _find_shift_break_or_404(shift_id)
    metadata = {
        "shift_id": shift.id,
        "start_at": target_break.start_at.isoformat() if target_break.start_at else None,
        "end_at": target_break.end_at.isoformat() if target_break.end_at else None,
    }

    db.session.delete(target_break)
    db.session.commit()
    log_audit("admin_break_delete", target_type="break", target_id=break_id, metadata_dict=metadata)
    flash("休憩を削除しました", "success")
    return redirect(url_for("admin.shift_edit", shift_id=shift_id))


def _handle_break_reset_action(shift, shift_id):
    deleted_ids = [br.id for br in shift.breaks]
    for br in list(shift.breaks):
        db.session.delete(br)
    db.session.commit()

    log_audit(
        "admin_break_reset",
        target_type="shift",
        target_id=shift_id,
        metadata_dict={"deleted_break_ids": deleted_ids},
    )
    flash("休憩を全削除しました", "success")
    return redirect(url_for("admin.shift_edit", shift_id=shift_id))


def _handle_shift_edit_action(action, shift, shift_id):
    handlers = {
        "update_shift": _handle_shift_update_action,
        "break_add": _handle_break_add_action,
        "break_update": _handle_break_update_action,
        "break_delete": _handle_break_delete_action,
        "break_reset": _handle_break_reset_action,
    }
    handler = handlers.get(action)
    if not handler:
        flash("不明な操作です", "error")
        return None
    return handler(shift, shift_id)


def _handle_user_create_action():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    role = request.form.get("role", "user")

    if not username or not password:
        flash("ユーザーIDとパスワードは必須です", "error")
        return redirect(url_for("admin.users"))

    if User.query.filter_by(username=username).first():
        flash("そのユーザーIDは既に使用されています", "error")
        return redirect(url_for("admin.users"))
    if email and User.query.filter_by(email=email).first():
        flash("そのメールアドレスは既に使用されています", "error")
        return redirect(url_for("admin.users"))

    user = User(username=username, name=name or None, email=email or None, role=role)
    user.set_password(password)
    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("ユーザー作成に失敗しました。入力内容を確認してください", "error")
        return redirect(url_for("admin.users"))

    log_audit(
        "admin_user_create",
        target_type="user",
        target_id=user.id,
        metadata_dict={"username": username, "role": role},
    )
    flash("ユーザーを作成しました", "success")
    return redirect(url_for("admin.users"))


def _handle_user_update_action():
    user_id = request.form.get("user_id")
    user = User.query.get_or_404(user_id)

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    role = request.form.get("role", "user")
    password = request.form.get("password", "").strip()

    if email:
        existing = User.query.filter(User.email == email, User.id != user.id).first()
        if existing:
            flash("そのメールアドレスは既に使用されています", "error")
            return redirect(url_for("admin.users"))

    user.name = name or None
    user.email = email or None
    user.role = role
    if password:
        user.set_password(password)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("ユーザー更新に失敗しました。入力内容を確認してください", "error")
        return redirect(url_for("admin.users"))

    log_audit(
        "admin_user_update",
        target_type="user",
        target_id=user.id,
        metadata_dict={
            "username": user.username,
            "role": role,
            "password_changed": bool(password),
        },
    )
    flash("ユーザーを更新しました", "success")
    return redirect(url_for("admin.users"))


def _handle_user_delete_action():
    user_id = request.form.get("user_id")
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("自分自身は削除できません", "error")
        return redirect(url_for("admin.users"))

    username = user.username
    AuditLog.query.filter_by(user_id=user.id).update({"user_id": None})
    db.session.delete(user)
    db.session.commit()

    log_audit(
        "admin_user_delete",
        target_type="user",
        target_id=user_id,
        metadata_dict={"username": username},
    )
    flash("ユーザーを削除しました", "success")
    return redirect(url_for("admin.users"))


def _handle_users_action(action):
    handlers = {
        "create": _handle_user_create_action,
        "update": _handle_user_update_action,
        "delete": _handle_user_delete_action,
    }
    handler = handlers.get(action)
    if not handler:
        flash("不明な操作です", "error")
        return redirect(url_for("admin.users"))
    return handler()


@bp.route("")
@bp.route("/")
@login_required
def dashboard():
    require_admin()
    ensure_csrf()
    react_response = _serve_react_if_enabled()
    if react_response:
        return react_response

    start = request.args.get("start")
    end = request.args.get("end")
    user_username = request.args.get("username", "").strip()
    try:
        context = build_admin_overview(start, end, user_username, include_candidates=True)
    except ValueError as exc:
        abort(400, str(exc))

    return render_template("admin.html", **context)


@bp.route("/shift/create", methods=["POST"])
@login_required
def shift_create():
    require_admin()
    verify_csrf()

    try:
        user_id = request.form.get("user_id")
        if not user_id:
            raise ValueError("対象ユーザーを選択してください")

        user = User.query.get(user_id)
        if not user:
            raise ValueError("対象ユーザーが見つかりません")

        clock_in_at, clock_out_at = _parse_shift_datetimes(request.form)
        shift = Shift(
            user_id=user.id,
            clock_in_at=clock_in_at,
            clock_out_at=clock_out_at,
            clock_in_ip=client_ip(),
            clock_in_ua=user_agent(),
            clock_out_ip=client_ip() if clock_out_at else None,
            clock_out_ua=user_agent() if clock_out_at else None,
        )
        db.session.add(shift)
        db.session.commit()

        log_audit(
            "admin_shift_create",
            target_type="shift",
            target_id=shift.id,
            metadata_dict={
                "user_username": user.username,
                "clock_in_at": shift.clock_in_at.isoformat() if shift.clock_in_at else None,
                "clock_out_at": shift.clock_out_at.isoformat() if shift.clock_out_at else None,
            },
        )
        flash("勤務記録を作成しました", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to create shift: %s", exc)
        flash("勤務記録の作成に失敗しました", "error")

    return _admin_redirect_with_filters()


@bp.route("/shift/<int:shift_id>/delete", methods=["POST"])
@login_required
def shift_delete(shift_id):
    require_admin()
    verify_csrf()

    shift = Shift.query.get_or_404(shift_id)
    metadata = {
        "user_username": shift.user.username if shift.user else None,
        "clock_in_at": shift.clock_in_at.isoformat() if shift.clock_in_at else None,
        "clock_out_at": shift.clock_out_at.isoformat() if shift.clock_out_at else None,
        "break_count": len(shift.breaks),
        "worked_seconds": shift.worked_seconds(),
    }

    try:
        db.session.delete(shift)
        db.session.commit()
        log_audit("admin_shift_delete", target_type="shift", target_id=shift_id, metadata_dict=metadata)
        flash("勤務記録を削除しました", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to delete shift: %s", exc)
        flash("勤務記録の削除に失敗しました", "error")

    return _admin_redirect_with_filters()


@bp.route("/export")
@login_required
def export_csv():
    require_admin()

    start = request.args.get("start")
    end = request.args.get("end")
    user_email = request.args.get("email", "").strip().lower()
    user_username = request.args.get("username", "").strip()

    now_local = datetime.now(LOCAL_TZ)
    default_end = now_local.date()
    default_start = default_end - timedelta(days=13)

    try:
        start_date = datetime.fromisoformat(start).date() if start else default_start
        end_date = datetime.fromisoformat(end).date() if end else default_end
    except ValueError:
        abort(400, "日付の形式が不正です。YYYY-MM-DD で指定してください。")

    try:
        start_date, end_date = ensure_valid_range(start_date, end_date)
    except ValueError as exc:
        abort(400, str(exc))

    csv_data, shift_count = generate_attendance_csv(
        start_date,
        end_date,
        user_username if user_username else None,
        user_email if user_email else None,
    )

    filename = f"attendance_export_{start_date.isoformat()}_{end_date.isoformat()}.csv"
    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"

    log_audit(
        "admin_export",
        target_type="shift",
        target_id=None,
        metadata_dict={
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "email": user_email,
            "shift_count": shift_count,
        },
    )
    return response


@bp.route("/shift/<int:shift_id>/edit", methods=["GET", "POST"])
@login_required
def shift_edit(shift_id):
    require_admin()
    ensure_csrf()
    if request.method == "GET":
        react_response = _serve_react_if_enabled()
        if react_response:
            return react_response

    shift = Shift.query.get_or_404(shift_id)

    if request.method == "POST":
        verify_csrf()
        action = request.form.get("action", "update_shift")

        try:
            response = _handle_shift_edit_action(action, shift, shift_id)
            if response is not None:
                return response
        except ValueError as exc:
            flash(str(exc), "error")
        except HTTPException:
            raise
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception("Failed to update shift: %s", exc)
            flash("勤務記録の更新に失敗しました", "error")

    context = build_shift_edit_context(shift)
    return render_template(
        "shift_edit.html",
        shift=shift,
        clock_in_form=context["clock_in_form"],
        clock_out_form=context["clock_out_form"],
        break_entries=context["break_entries"],
        LOCAL_TZ_NAME=str(LOCAL_TZ),
    )


@bp.route("/shift/<int:shift_id>", methods=["GET"])
@login_required
def shift_detail(shift_id):
    require_admin()
    shift = Shift.query.get_or_404(shift_id)
    return jsonify(build_shift_detail_payload(shift))


@bp.route("/users", methods=["GET", "POST"])
@login_required
def users():
    require_admin()
    ensure_csrf()
    if request.method == "GET":
        react_response = _serve_react_if_enabled()
        if react_response:
            return react_response

    if request.method == "POST":
        verify_csrf()
        return _handle_users_action(request.form.get("action"))

    users = User.query.order_by(User.username.asc()).all()
    return render_template("admin_users.html", users=users)
