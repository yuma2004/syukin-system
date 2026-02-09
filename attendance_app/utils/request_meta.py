from flask import current_app, request


def client_ip():
    trust_forwarded_for = bool(current_app.config.get("TRUST_X_FORWARDED_FOR", False))
    if trust_forwarded_for and request.access_route:
        return request.access_route[0]
    return request.remote_addr or "?"


def user_agent():
    return request.headers.get("User-Agent", "?")[:300]
