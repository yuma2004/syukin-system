import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_TEST_DB_PATH = Path(tempfile.gettempdir()) / f"syukin_system_test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("TIMEZONE", "Asia/Tokyo")

from app import AuditLog, Break, Shift, User, app as flask_app, db  # noqa: E402


def _set_csrf_token(client, token="test-csrf-token"):
    with client.session_transaction() as session:
        session["csrf_token"] = token
    return token


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_db_file():
    yield
    with flask_app.app_context():
        db.session.remove()
        db.engine.dispose()
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink(missing_ok=True)


@pytest.fixture
def app():
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture(autouse=True)
def _reset_database(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def set_csrf_token():
    return _set_csrf_token


@pytest.fixture
def create_user(app):
    def _create(
        *,
        username,
        password="password123",
        role="user",
        name=None,
        email=None,
    ):
        with app.app_context():
            user = User(
                username=username,
                role=role,
                name=name,
                email=email,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            return user.id

    return _create


@pytest.fixture
def login_as(client, create_user, set_csrf_token):
    def _login(
        *,
        username,
        password="password123",
        role="user",
        name=None,
        email=None,
    ):
        user_id = create_user(
            username=username,
            password=password,
            role=role,
            name=name,
            email=email,
        )
        token = set_csrf_token(client)
        response = client.post(
            "/login",
            data={
                "username": username,
                "password": password,
                "csrf_token": token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        return user_id

    return _login


@pytest.fixture
def login_as_admin(login_as):
    def _login(*, username="admin", password="admin-password", name=None, email=None):
        return login_as(
            username=username,
            password=password,
            role="admin",
            name=name,
            email=email,
        )

    return _login


@pytest.fixture
def create_shift(app):
    def _create(
        *,
        user_id,
        clock_in_at=None,
        clock_out_at=None,
        break_start_at=None,
        break_end_at=None,
    ):
        with app.app_context():
            clock_in = clock_in_at or datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
            shift = Shift(
                user_id=user_id,
                clock_in_at=clock_in,
                clock_out_at=clock_out_at,
            )
            db.session.add(shift)
            db.session.commit()

            if break_start_at is not None or break_end_at is not None:
                start_at = break_start_at or (clock_in + timedelta(hours=1))
                new_break = Break(
                    shift_id=shift.id,
                    start_at=start_at,
                    end_at=break_end_at,
                )
                db.session.add(new_break)
                db.session.commit()

            return shift.id

    return _create


@pytest.fixture
def create_audit_log(app):
    def _create(
        *,
        action,
        user_id=None,
        target_type=None,
        target_id=None,
        ip="127.0.0.1",
        user_agent="pytest-agent",
        metadata_dict=None,
        metadata_json=None,
        signature="test-signature",
        created_at=None,
    ):
        with app.app_context():
            if metadata_json is None:
                if metadata_dict is None:
                    metadata_json_value = "{}"
                else:
                    import json

                    metadata_json_value = json.dumps(metadata_dict, ensure_ascii=False, separators=(",", ":"))
            else:
                metadata_json_value = metadata_json

            entry = AuditLog(
                user_id=user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                ip=ip,
                user_agent=user_agent,
                metadata_json=metadata_json_value,
                signature=signature,
                created_at=created_at or datetime.now(timezone.utc),
            )
            db.session.add(entry)
            db.session.commit()
            return entry.id

    return _create


@pytest.fixture
def list_audit_logs(app):
    def _list(*, action=None):
        with app.app_context():
            query = AuditLog.query.order_by(AuditLog.id.asc())
            if action:
                query = query.filter_by(action=action)
            return query.all()

    return _list
