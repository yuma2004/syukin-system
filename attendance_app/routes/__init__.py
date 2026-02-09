from .admin import bp as admin_bp
from .attendance import bp as attendance_bp
from .audit import bp as audit_bp
from .auth import bp as auth_bp
from .health import bp as health_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(health_bp)
