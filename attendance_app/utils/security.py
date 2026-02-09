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

    form_token = request.form.get("csrf_token", "")
    session_token = session.get("csrf_token")
    valid = form_token and session_token and secrets.compare_digest(form_token, session_token)
    if not valid:
        abort(400, "CSRF token missing or invalid")
