from pathlib import Path

from flask import Flask, current_app, jsonify, redirect, request, url_for
from flask_login import current_user
from sqlalchemy import inspect
from werkzeug.middleware.proxy_fix import ProxyFix

from .cli import register_cli
from .config import LOCAL_TZ, build_base_config
from .extensions import db, login_manager
from .models import User
from .routes import register_blueprints
from .utils.datetime_utils import fmt_date_ja, fmt_dt, fmt_hms
from .utils.dev_seed import seed_dev_users_if_enabled
from .utils.security import ensure_csrf, verify_csrf


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except (TypeError, ValueError):
        return None


def _find_legacy_sqlite_path(app, sqlite_path):
    """
    Keep backward compatibility with the old relative-path behavior.

    Historically, `sqlite:///attendance.db` was often resolved from the project
    root. If such a legacy file exists, continue using it.
    """
    project_root = Path(app.root_path).resolve().parent
    candidates = [(project_root / sqlite_path).resolve()]
    seen = set()
    for candidate in candidates:
        key = candidate.as_posix()
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return candidate
    return None


def _normalize_sqlite_uri(app):
    uri = app.config.get("SQLALCHEMY_DATABASE_URI")
    if not isinstance(uri, str):
        return

    prefix = "sqlite:///"
    if not uri.startswith(prefix):
        return

    sqlite_path = uri[len(prefix) :]
    if not sqlite_path or sqlite_path in {":memory:"} or sqlite_path.startswith("file:"):
        return

    if Path(sqlite_path).is_absolute():
        return

    # Resolve relative sqlite paths from the project root to avoid "DB moved"
    # surprises when running the app from different working directories.
    project_root = Path(app.root_path).resolve().parent
    absolute_default = (project_root / sqlite_path).resolve()
    absolute_default.parent.mkdir(parents=True, exist_ok=True)
    legacy_path = _find_legacy_sqlite_path(app, sqlite_path)
    absolute_path = legacy_path or absolute_default
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{absolute_path.as_posix()}"


def _ensure_local_schema(app):
    uri = app.config.get("SQLALCHEMY_DATABASE_URI")
    if not isinstance(uri, str) or not uri.startswith("sqlite:///"):
        return
    if app.config.get("TESTING"):
        return

    required_tables = {"users", "shifts", "breaks", "audit_logs"}
    with app.app_context():
        existing_tables = set(inspect(db.engine).get_table_names())
        if not required_tables.issubset(existing_tables):
            db.create_all()


_CSRF_PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _install_csrf_protection(app):
    @app.before_request
    def _csrf_guard():
        ensure_csrf()
        if request.method in _CSRF_PROTECTED_METHODS:
            verify_csrf()


def _api_unauthorized():
    return jsonify({"ok": False, "error": {"message": "login required"}}), 401


def _serve_spa_index(app):
    return app.send_static_file("spa/index.html")


def create_app(test_config=None):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1)

    app.config.from_mapping(build_base_config())
    if test_config:
        app.config.update(test_config)
    _normalize_sqlite_uri(app)

    db.init_app(app)
    _ensure_local_schema(app)
    seed_dev_users_if_enabled(app)
    login_manager.init_app(app)
    _install_csrf_protection(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "このページにアクセスするにはログインしてください。"
    login_manager.login_message_category = "warning"
    login_manager.needs_refresh_message = "この操作を続けるには再ログインしてください。"
    login_manager.needs_refresh_message_category = "warning"

    app.add_template_filter(fmt_dt, "fmt_dt")
    app.add_template_filter(fmt_hms, "fmt_hms")
    app.add_template_filter(fmt_date_ja, "fmt_date_ja")

    @login_manager.unauthorized_handler
    def _login_required_handler():
        if request.path == "/api" or request.path.startswith("/api/"):
            return _api_unauthorized()
        return redirect(url_for("auth.login"))

    @app.context_processor
    def inject_globals():
        return {
            "current_user": current_user,
            "is_admin": (current_user.is_authenticated and current_user.is_admin()),
            "LOCAL_TZ_NAME": str(LOCAL_TZ),
        }

    register_blueprints(app)
    register_cli(app)

    @app.get("/app", defaults={"path": ""})
    @app.get("/app/<path:path>")
    def serve_react_app(path=None):  # noqa: ARG001
        if not current_app.config.get("REACT_UI_ENABLED"):
            return redirect(url_for("auth.login"))
        return _serve_spa_index(app)

    @app.get("/favicon.ico")
    def favicon():
        return app.send_static_file("favicon.svg")

    return app

