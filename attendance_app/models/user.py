from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(320), unique=True, nullable=True, index=True)
    name = db.Column(db.String(200))
    picture = db.Column(db.String(500))
    role = db.Column(db.String(20), default="user")
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login_at = db.Column(db.DateTime(timezone=True))
    shifts = db.relationship(
        "Shift",
        backref=db.backref("user", lazy=True),
        lazy=True,
        cascade="all, delete-orphan",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == "admin"
