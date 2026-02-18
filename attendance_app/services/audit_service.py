import json
import logging

from flask import has_app_context, has_request_context
from flask_login import current_user

from ..extensions import db
from ..models import AuditLog
from ..utils.request_meta import client_ip, user_agent
from ..utils.security import sign_payload


def _resolve_request_actor(user_id, ip, user_agent_str):
    if has_request_context():
        derived_user_id = current_user.get_id() if current_user.is_authenticated else None
        derived_ip = client_ip()
        derived_ua = user_agent()
    else:
        derived_user_id = None
        derived_ip = None
        derived_ua = None

    return (
        user_id if user_id is not None else derived_user_id,
        ip if ip is not None else derived_ip,
        user_agent_str if user_agent_str is not None else derived_ua,
    )


def log_audit(
    action,
    target_type=None,
    target_id=None,
    metadata_dict=None,
    *,
    user_id=None,
    ip=None,
    user_agent_str=None,
    commit=True,
):
    try:
        metadata_json = json.dumps(metadata_dict or {}, ensure_ascii=False, separators=(",", ":"))
        signature = sign_payload(f"{action}|{target_type}|{target_id}|{metadata_json}")
        resolved_user_id, resolved_ip, resolved_ua = _resolve_request_actor(user_id, ip, user_agent_str)

        entry = AuditLog(
            user_id=resolved_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip=resolved_ip,
            user_agent=resolved_ua,
            metadata_json=metadata_json,
            signature=signature,
        )
        db.session.add(entry)
        if commit:
            db.session.commit()
    except Exception as exc:
        if has_app_context():
            from flask import current_app

            current_app.logger.exception("Audit log failed: %s", exc)
            return
        logging.getLogger(__name__).exception("Audit log failed without app context: %s", exc)
