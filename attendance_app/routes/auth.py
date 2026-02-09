from datetime import datetime, timezone

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from ..extensions import db
from ..models import User
from ..services.audit_service import log_audit
from ..utils.security import ensure_csrf, verify_csrf

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    ensure_csrf()
    if request.method == "POST":
        verify_csrf()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("ユーザーIDとパスワードを入力してください。", "error")
            return redirect(url_for("auth.login"))

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            remember_me = request.form.get("remember_me") in {"1", "true", "on"}
            user.last_login_at = datetime.now(timezone.utc)
            db.session.commit()
            login_user(user, remember=remember_me)
            log_audit("login", target_type="user", target_id=user.id, metadata_dict={"username": username})
            flash("ログインしました。", "success")
            return redirect(url_for("attendance.dashboard"))

        flash("ユーザーIDまたはパスワードが正しくありません。", "error")
        return redirect(url_for("auth.login"))

    remember_days = current_app.config["REMEMBER_COOKIE_DURATION"].days
    return render_template("login.html", remember_days=remember_days)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    from flask_login import current_user

    verify_csrf()
    log_audit("logout", target_type="user", target_id=current_user.id)
    logout_user()
    return redirect(url_for("auth.login"))
