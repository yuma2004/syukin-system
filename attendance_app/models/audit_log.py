from datetime import datetime, timezone

from ..extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user = db.relationship("User", backref="audit_logs")
    action = db.Column(db.String(50), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    ip = db.Column(db.String(100))
    user_agent = db.Column(db.String(300))
    metadata_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    signature = db.Column(db.String(128))
