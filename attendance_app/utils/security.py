from flask import abort, current_app, request, session
import hmac
import secrets
import hashlib


def sign_payload(payload):
    key = str(current_app.config["SECRET_KEY"]).encode("utf-8")
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def ensure_csrf():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def verify_csrf():
    if not current_app.config.get("WTF_CSRF_ENABLED", True):
        return

    token = request.form.get("csrf_token", "")
    if not token:
        token = request.headers.get("X-CSRF-Token", "")
    if not token and request.is_json:
        payload = request.get_json(silent=True) or {}
        token = payload.get("csrf_token", "")

    session_token = session.get("csrf_token")
    valid = token and session_token and secrets.compare_digest(token, session_token)
    if not valid:
        abort(400, "CSRF token missing or invalid")
