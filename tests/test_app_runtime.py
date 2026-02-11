from app import env_bool
from attendance_app import _normalize_sqlite_uri
from flask import Flask


def test_env_bool_returns_default_for_missing_value(monkeypatch):
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert env_bool("FLASK_DEBUG", False) is False


def test_env_bool_parses_truthy_values(monkeypatch):
    monkeypatch.setenv("FLASK_DEBUG", "true")
    assert env_bool("FLASK_DEBUG", False) is True


def test_normalize_sqlite_uri_prefers_legacy_db_path(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    package_root = project_root / "attendance_app"
    instance_dir = project_root / "instance"
    package_root.mkdir(parents=True)
    legacy_db = project_root / "attendance.db"
    legacy_db.touch()

    monkeypatch.chdir(project_root)
    app = Flask(
        "test-app",
        root_path=str(package_root),
        instance_path=str(instance_dir),
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///attendance.db"

    _normalize_sqlite_uri(app)

    assert app.config["SQLALCHEMY_DATABASE_URI"] == f"sqlite:///{legacy_db.as_posix()}"


def test_normalize_sqlite_uri_uses_project_root_when_legacy_missing(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    package_root = project_root / "attendance_app"
    instance_dir = project_root / "instance"
    package_root.mkdir(parents=True)

    monkeypatch.chdir(project_root)
    app = Flask(
        "test-app",
        root_path=str(package_root),
        instance_path=str(instance_dir),
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///attendance.db"

    _normalize_sqlite_uri(app)

    expected = (project_root / "attendance.db").resolve().as_posix()
    assert app.config["SQLALCHEMY_DATABASE_URI"] == f"sqlite:///{expected}"


def test_login_page_uses_desktop_only_initial_focus(client):
    response = client.get("/login")
    html = response.get_data(as_text=True)

    assert "autofocus" not in html
    assert 'matchMedia("(pointer: fine)")' in html


def test_layout_includes_theme_color_and_favicon(client):
    response = client.get("/login")
    html = response.get_data(as_text=True)

    assert 'name="theme-color"' in html
    assert 'rel="icon"' in html
    assert "favicon.svg" in html


def test_favicon_is_served(client):
    response = client.get("/static/favicon.svg")
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"


def test_favicon_ico_route_is_served(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 200


def test_admin_user_edit_modal_has_focus_target_and_autocomplete(client, logged_in_admin):
    response = client.get("/admin/users")
    html = response.get_data(as_text=True)

    assert 'id="edit-username"' in html
    assert 'id="edit-username" disabled autocomplete="username"' in html
    assert "data-modal-initial-focus" in html


def test_admin_shift_modal_has_focus_target(client, logged_in_admin):
    response = client.get("/admin")
    html = response.get_data(as_text=True)

    assert 'id="shiftEditClockIn"' in html
    assert 'id="shiftEditClockIn" name="clock_in_at" step="60" required data-modal-initial-focus' in html


def test_admin_attendance_dashboard_uses_admin_shell_layout(client, logged_in_admin):
    response = client.get("/dashboard")
    html = response.get_data(as_text=True)

    assert "admin-app-layout" in html
    assert "admin-app-sidebar" in html
