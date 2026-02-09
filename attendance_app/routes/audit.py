import json
from datetime import datetime

from flask import Blueprint, make_response, render_template, request
from flask_login import login_required

from ..authz import require_admin
from ..config import LOCAL_TZ
from ..extensions import db
from ..models import AuditLog, User
from ..services.audit_service import log_audit
from ..services.csv_service import generate_audit_csv
from ..utils.security import ensure_csrf

bp = Blueprint("audit", __name__)


def _parse_audit_filters(max_limit=500, default_limit=200):
    action = request.args.get("action", "").strip()
    username = request.args.get("username", "").strip()
    try:
        limit = int(request.args.get("limit", str(default_limit)))
    except ValueError:
        limit = default_limit
    limit = max(1, min(limit, max_limit))
    return action, username, limit


def _audit_log_query(action, username):
    query = AuditLog.query.order_by(AuditLog.created_at.desc())
    if action:
        query = query.filter(AuditLog.action == action)
    if username:
        query = query.join(User).filter(User.username == username)
    return query


@bp.route("/admin/audit")
@login_required
def view_logs():
    require_admin()
    ensure_csrf()

    action, username, limit = _parse_audit_filters()
    logs = _audit_log_query(action, username).limit(limit).all()

    action_rows = db.session.query(AuditLog.action).distinct().order_by(AuditLog.action.asc()).all()
    action_choices = [row[0] for row in action_rows]
    user_candidates = User.query.order_by(User.username.asc()).all()

    log_entries = []
    for log in logs:
        try:
            metadata = json.loads(log.metadata_json) if log.metadata_json else {}
        except Exception:
            metadata = {"raw": log.metadata_json}
        log_entries.append({"log": log, "metadata": metadata})

    return render_template(
        "admin_audit.html",
        log_entries=log_entries,
        action_choices=action_choices,
        selected_action=action,
        selected_username=username,
        limit=limit,
        user_candidates=user_candidates,
    )


@bp.route("/admin/audit/export")
@login_required
def export_logs():
    require_admin()

    action, username, limit = _parse_audit_filters(max_limit=5000, default_limit=1000)
    logs = _audit_log_query(action, username).limit(limit).all()

    csv_data = generate_audit_csv(logs)
    filename = f"audit_export_{datetime.now(LOCAL_TZ).strftime('%Y%m%d_%H%M%S')}.csv"

    response = make_response(csv_data)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"

    log_audit(
        "admin_audit_export",
        target_type="audit_log",
        target_id=None,
        metadata_dict={
            "action": action or None,
            "username": username or None,
            "limit": limit,
            "count": len(logs),
        },
    )

    return response
