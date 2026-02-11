import click

from . import models
from .extensions import db


def register_cli(app):
    @app.cli.command("init-db")
    def init_db_command():
        """Create all database tables."""
        if not models.__all__:
            raise RuntimeError("No models are registered for database initialization.")
        db.create_all()
        click.echo("Initialized the database.")

    @app.cli.command("seed-dev-users")
    @click.option(
        "--reset-passwords",
        is_flag=True,
        help="Also reset passwords for existing dev users.",
    )
    def seed_dev_users_command(reset_passwords):
        """Create or update dev users (for local development)."""
        from .utils.dev_seed import seed_dev_users

        if not app.config.get("ALLOW_DEV_LOGIN"):
            click.echo("WARN: ALLOW_DEV_LOGIN is false. Seeding anyway because CLI was invoked.")

        with app.app_context():
            result = seed_dev_users(reset_passwords=reset_passwords)
        click.echo(f"Seeded dev users. created={result.created} updated={result.updated}")
