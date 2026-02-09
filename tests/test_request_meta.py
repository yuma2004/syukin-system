from app import app
from attendance_app.utils.request_meta import client_ip


def test_client_ip_uses_remote_addr_by_default():
    original = app.config.get("TRUST_X_FORWARDED_FOR", False)
    app.config["TRUST_X_FORWARDED_FOR"] = False
    try:
        with app.test_request_context(
            "/",
            headers={"X-Forwarded-For": "203.0.113.10"},
            environ_overrides={"REMOTE_ADDR": "10.0.0.8"},
        ):
            assert client_ip() == "10.0.0.8"
    finally:
        app.config["TRUST_X_FORWARDED_FOR"] = original


def test_client_ip_can_trust_forwarded_for_when_enabled():
    original = app.config.get("TRUST_X_FORWARDED_FOR", False)
    app.config["TRUST_X_FORWARDED_FOR"] = True
    try:
        with app.test_request_context(
            "/",
            headers={"X-Forwarded-For": "203.0.113.10, 198.51.100.4"},
            environ_overrides={"REMOTE_ADDR": "10.0.0.8"},
        ):
            assert client_ip() == "203.0.113.10"
    finally:
        app.config["TRUST_X_FORWARDED_FOR"] = original
