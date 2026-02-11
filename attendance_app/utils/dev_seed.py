from __future__ import annotations

from dataclasses import dataclass

from flask import current_app

from ..extensions import db
from ..models import User


@dataclass(frozen=True)
class DevSeedResult:
    created: int
    updated: int


def _safe_set_email(user: User, email: str | None) -> bool:
    if not email:
        user.email = None
        return True

    existing = User.query.filter_by(email=email).first()
    if existing and existing.username != user.username:
        current_app.logger.warning(
            "Dev seed: email %s is already used by %s; leaving %s email unchanged.",
            email,
            existing.username,
            user.username,
        )
        return False

    user.email = email
    return True


def seed_dev_users(*, reset_passwords: bool = False) -> DevSeedResult:
    """Create or update dev users in-place (idempotent).

    This must only be used in development environments. Always gate it with
    `ALLOW_DEV_LOGIN` or an explicit CLI invocation.
    """
    db.create_all()

    cfg = current_app.config
    created = 0
    updated = 0

    def upsert_user(*, username: str, password: str, role: str, name: str, email: str | None) -> None:
        nonlocal created, updated

        user = User.query.filter_by(username=username).first()
        is_new = user is None
        changed = False

        if is_new:
            user = User(username=username, role=role)
            user.set_password(password)
            db.session.add(user)
            created += 1
            changed = True

        if user.role != role:
            user.role = role
            changed = True

        if name and user.name != name:
            user.name = name
            changed = True

        before_email = user.email
        if _safe_set_email(user, email) and user.email != before_email:
            changed = True

        if reset_passwords or not user.password_hash:
            user.set_password(password)
            changed = True

        if changed and not is_new:
            updated += 1

    upsert_user(
        username=str(cfg.get("DEV_ADMIN_USERNAME", "admin")),
        password=str(cfg.get("DEV_ADMIN_PASSWORD", "adminpass123")),
        role="admin",
        name=str(cfg.get("DEV_ADMIN_NAME", "Admin User")),
        email=cfg.get("DEV_ADMIN_EMAIL", "admin@example.com"),
    )
    upsert_user(
        username=str(cfg.get("DEV_TEST_USERNAME", "testuser")),
        password=str(cfg.get("DEV_TEST_PASSWORD", "testpass123")),
        role="user",
        name=str(cfg.get("DEV_TEST_NAME", "Test User")),
        email=cfg.get("DEV_TEST_EMAIL", "test@example.com"),
    )

    db.session.commit()
    return DevSeedResult(created=created, updated=updated)


def seed_dev_users_if_enabled(app) -> DevSeedResult | None:
    if app.config.get("TESTING"):
        return None
    if not app.config.get("ALLOW_DEV_LOGIN"):
        return None

    reset_passwords = bool(app.config.get("DEV_SEED_RESET_PASSWORDS"))
    with app.app_context():
        try:
            result = seed_dev_users(reset_passwords=reset_passwords)
        except Exception:  # pragma: no cover - defensive: don't block app boot
            app.logger.exception("Dev user seeding failed.")
            return None

    if result.created or result.updated:
        app.logger.info("Dev users ensured. created=%s updated=%s", result.created, result.updated)
    return result
