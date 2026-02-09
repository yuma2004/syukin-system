from flask import abort
from flask_login import current_user


def require_admin():
    if not (current_user.is_authenticated and current_user.is_admin()):
        abort(403, "管理者のみアクセス可能です。")
