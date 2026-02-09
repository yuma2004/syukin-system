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
