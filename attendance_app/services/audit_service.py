import json

from flask import has_request_context
from flask_login import current_user

from ..extensions import db
from ..models import AuditLog
from ..utils.request_meta import client_ip, user_agent
from ..utils.security import sign_payload


def log_audit(
    action,
    target_type=None,
    target_id=None,
    metadata_dict=None,
    *,
    user_id=None,
    ip=None,
    user_agent_str=None,
):
    try:
        metadata_json = json.dumps(metadata_dict or {}, ensure_ascii=False, separators=(",", ":"))
        signature = sign_payload(f"{action}|{target_type}|{target_id}|{metadata_json}")

        if has_request_context():
            derived_user_id = current_user.get_id() if current_user.is_authenticated else None
            derived_ip = client_ip()
            derived_ua = user_agent()
        else:
            derived_user_id = None
            derived_ip = None
            derived_ua = None

        entry = AuditLog(
            user_id=user_id if user_id is not None else derived_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip=ip if ip is not None else derived_ip,
            user_agent=user_agent_str if user_agent_str is not None else derived_ua,
            metadata_json=metadata_json,
            signature=signature,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as exc:
        from flask import current_app

        current_app.logger.exception("Audit log failed: %s", exc)
