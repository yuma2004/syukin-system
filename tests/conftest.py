"""
テスト設定とフィクスチャ
"""
import os
import tempfile
import pytest
import secrets
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# Windows環境でのパス問題を回避するため、app.pyを直接インポート
import sys
# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app, db, User, Shift, Break, AuditLog  # noqa: E402

@pytest.fixture(scope='session')
def app_config():
    """テスト用アプリケーション設定"""
    # 一時的なSQLiteデータベースを使用
    # Windows環境でのパス問題を回避するため、絶対パスを使用
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    # Windows環境でのパス問題を回避
    db_uri = f'sqlite:///{db_path.replace(os.sep, "/")}'
    
    config = {
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': db_uri,
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SECRET_KEY': 'test-secret-key-for-testing-only',
        'WTF_CSRF_ENABLED': False,  # テストではCSRFを無効化
    }
    
    yield config
    
    # クリーンアップ
    try:
        if os.path.exists(db_path):
            os.unlink(db_path)
    except Exception:
        pass

@pytest.fixture
def client(app_config):
    """テストクライアント"""
    # テスト用にCSRF検証を無効化するためのモンキーパッチ
    import app as app_module
    original_verify_csrf = app_module.verify_csrf
    
    def mock_verify_csrf():
        """テスト用のCSRF検証をスキップ"""
        pass
    
    # モンキーパッチを適用
    app_module.verify_csrf = mock_verify_csrf
    
    # Flaskアプリケーションインスタンスの設定を更新
    app.config.update(app_config)
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()
    
    # 元に戻す
    app_module.verify_csrf = original_verify_csrf

@pytest.fixture
def csrf_token(client):
    """CSRFトークンを取得するヘルパー"""
    with client.session_transaction() as sess:
        token = secrets.token_urlsafe(32)
        sess['csrf_token'] = token
        return token

@pytest.fixture
def test_user(client):
    """テスト用の通常ユーザー"""
    user = User.query.filter_by(username='testuser').first()
    if user is None:
        user = User(
            username='testuser',
            email='test@example.com',
            name='テストユーザー',
            role='user'
        )
        db.session.add(user)

    # 既存データが残っていても同じ資格情報に揃える
    user.email = 'test@example.com'
    user.name = 'テストユーザー'
    user.role = 'user'
    user.set_password('testpass123')
    db.session.commit()
    return user

@pytest.fixture
def admin_user(client):
    """テスト用の管理者ユーザー"""
    admin = User.query.filter_by(username='admin').first()
    if admin is None:
        admin = User(
            username='admin',
            email='admin@example.com',
            name='管理者',
            role='admin'
        )
        db.session.add(admin)

    # 既存データが残っていても同じ資格情報に揃える
    admin.email = 'admin@example.com'
    admin.name = '管理者'
    admin.role = 'admin'
    admin.set_password('adminpass123')
    db.session.commit()
    return admin

@pytest.fixture
def logged_in_user(client, test_user, csrf_token):
    """ログイン済みの通常ユーザー"""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_user.id)
        sess['csrf_token'] = csrf_token
    return test_user

@pytest.fixture
def logged_in_admin(client, admin_user, csrf_token):
    """ログイン済みの管理者ユーザー"""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['csrf_token'] = csrf_token
    return admin_user

@pytest.fixture
def sample_shift(client, test_user):
    """テスト用の出退勤記録"""
    now = datetime.now(timezone.utc)
    shift = Shift(
        user_id=test_user.id,
        clock_in_at=now - timedelta(hours=8),
        clock_out_at=now,
        clock_in_ip='127.0.0.1',
        clock_in_ua='Test User Agent'
    )
    db.session.add(shift)
    db.session.commit()
    return shift

@pytest.fixture
def open_shift(client, test_user):
    """テスト用の出勤中記録"""
    now = datetime.now(timezone.utc)
    shift = Shift(
        user_id=test_user.id,
        clock_in_at=now - timedelta(hours=2),
        clock_out_at=None,
        clock_in_ip='127.0.0.1',
        clock_in_ua='Test User Agent'
    )
    db.session.add(shift)
    db.session.commit()
    return shift

@pytest.fixture
def sample_break(client, open_shift):
    """テスト用の休憩記録"""
    now = datetime.now(timezone.utc)
    break_record = Break(
        shift_id=open_shift.id,
        start_at=now - timedelta(minutes=30),
        end_at=None,
        start_ip='127.0.0.1',
        start_ua='Test User Agent'
    )
    db.session.add(break_record)
    db.session.commit()
    return break_record

