from datetime import datetime, timezone

from ..extensions import db
from ..utils.datetime_utils import ensure_aware


class Shift(db.Model):
    __tablename__ = "shifts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    clock_in_at = db.Column(db.DateTime(timezone=True), nullable=False)
    clock_out_at = db.Column(db.DateTime(timezone=True), nullable=True)
    clock_in_ip = db.Column(db.String(100))
    clock_in_ua = db.Column(db.String(300))
    clock_out_ip = db.Column(db.String(100))
    clock_out_ua = db.Column(db.String(300))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    breaks = db.relationship("Break", backref="shift", lazy=True, cascade="all, delete-orphan")

    __table_args__ = (
        db.Index(
            "ix_shifts_user_open_unique",
            "user_id",
            unique=True,
            sqlite_where=(clock_out_at.is_(None)),
            postgresql_where=(clock_out_at.is_(None)),
        ),
    )

    @property
    def is_open(self):
        return self.clock_out_at is None

    def total_break_seconds(self, now=None):
        if now is None:
            now = datetime.now(timezone.utc)

        aware_now = ensure_aware(now)
        total = 0
        for br in self.breaks:
            start_at = ensure_aware(br.start_at)
            end_at = ensure_aware(br.end_at) if br.end_at else aware_now
            total += max(0, int((end_at - start_at).total_seconds()))
        return total

    def worked_seconds(self, now=None):
        if now is None:
            now = datetime.now(timezone.utc)

        start_at = ensure_aware(self.clock_in_at)
        end_at = ensure_aware(self.clock_out_at) if self.clock_out_at else ensure_aware(now)
        total = max(0, int((end_at - start_at).total_seconds()))
        total -= self.total_break_seconds(now=now)
        return max(0, total)

