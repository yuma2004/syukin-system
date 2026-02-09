from flask import Flask
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from .cli import register_cli
from .config import LOCAL_TZ, build_base_config
from .extensions import db, login_manager
from .models import User
from .routes import register_blueprints
from .utils.datetime_utils import fmt_date_ja, fmt_dt, fmt_hms
from .utils.security import ensure_csrf


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except (TypeError, ValueError):
        return None


def create_app(test_config=None):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1)

    app.config.from_mapping(build_base_config())
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    app.add_template_filter(fmt_dt, "fmt_dt")
    app.add_template_filter(fmt_hms, "fmt_hms")
    app.add_template_filter(fmt_date_ja, "fmt_date_ja")

    @app.context_processor
    def inject_globals():
        if current_user.is_authenticated:
            ensure_csrf()
        return {
            "current_user": current_user,
            "is_admin": (current_user.is_authenticated and current_user.is_admin()),
            "LOCAL_TZ_NAME": str(LOCAL_TZ),
        }

    register_blueprints(app)
    register_cli(app)
    return app

