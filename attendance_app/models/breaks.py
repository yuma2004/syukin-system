from ..extensions import db


class Break(db.Model):
    __tablename__ = "breaks"

    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False, index=True)
    start_at = db.Column(db.DateTime(timezone=True), nullable=False)
    end_at = db.Column(db.DateTime(timezone=True), nullable=True)
    start_ip = db.Column(db.String(100))
    start_ua = db.Column(db.String(300))
    end_ip = db.Column(db.String(100))
    end_ua = db.Column(db.String(300))

    __table_args__ = (
        db.Index(
            "ix_breaks_shift_open_unique",
            "shift_id",
            unique=True,
            sqlite_where=(end_at.is_(None)),
            postgresql_where=(end_at.is_(None)),
        ),
    )
