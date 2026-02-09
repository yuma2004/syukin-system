"""
監査ログ機能のテスト
"""
import pytest
from datetime import datetime, timezone
from app import User, AuditLog, db
from app import log_audit

class TestAuditLog:
    """監査ログ機能のテスト"""
    
    def test_admin_audit_page(self, client, logged_in_admin):
        """監査ログページが表示される"""
        response = client.get('/admin/audit')
        assert response.status_code == 200
    
    def test_admin_audit_requires_admin(self, client, logged_in_user):
        """通常ユーザーは監査ログページにアクセス不可"""
        response = client.get('/admin/audit')
        assert response.status_code == 403
    
    def test_audit_log_creation(self, client, test_user):
        """監査ログが作成される"""
        initial_count = AuditLog.query.count()
        
        log_audit(
            'test_action',
            target_type='test',
            target_id=1,
            metadata_dict={'key': 'value'},
            user_id=test_user.id,
            ip='127.0.0.1',
            user_agent_str='Test Agent'
        )
        
        assert AuditLog.query.count() == initial_count + 1
        
        log = AuditLog.query.order_by(AuditLog.id.desc()).first()
        assert log.action == 'test_action'
        assert log.target_type == 'test'
        assert log.user_id == test_user.id
        assert log.signature is not None
    
    def test_audit_log_signature(self, client, test_user):
        """監査ログに署名が付与される"""
        log_audit('test_action', user_id=test_user.id)
        
        log = AuditLog.query.order_by(AuditLog.id.desc()).first()
        assert log.signature is not None
        assert len(log.signature) > 0
    
    def test_audit_log_metadata(self, client, test_user):
        """監査ログにメタデータが保存される"""
        metadata = {
            'username': 'testuser',
            'ip': '127.0.0.1',
            'custom_field': 'custom_value'
        }
        
        log_audit(
            'test_action',
            metadata_dict=metadata,
            user_id=test_user.id
        )
        
        log = AuditLog.query.order_by(AuditLog.id.desc()).first()
        assert log.metadata_json is not None
        import json
        parsed = json.loads(log.metadata_json)
        assert parsed['username'] == 'testuser'
    
    def test_audit_log_without_user(self, client):
        """ユーザーなしで監査ログを作成"""
        log_audit('system_action', ip='127.0.0.1')
        
        log = AuditLog.query.order_by(AuditLog.id.desc()).first()
        assert log.user_id is None
        assert log.action == 'system_action'
    
    def test_admin_audit_filter_by_action(self, client, logged_in_admin, test_user):
        """アクションでフィルタ"""
        log_audit('action1', user_id=test_user.id)
        log_audit('action2', user_id=test_user.id)
        
        response = client.get('/admin/audit?action=action1')
        assert response.status_code == 200
    
    def test_admin_audit_filter_by_username(self, client, logged_in_admin, test_user):
        """ユーザー名でフィルタ"""
        log_audit('test_action', user_id=test_user.id)
        
        response = client.get(f'/admin/audit?username={test_user.username}')
        assert response.status_code == 200
    
    def test_admin_audit_export(self, client, logged_in_admin, test_user):
        """監査ログのCSVエクスポート"""
        log_audit('export_test', user_id=test_user.id)
        
        response = client.get('/admin/audit/export')
        
        assert response.status_code == 200
        assert response.content_type == 'text/csv; charset=utf-8'
        assert b'created_at_local' in response.data or b'action' in response.data
    
    def test_audit_log_on_login(self, client, test_user):
        """ログイン時に監査ログが記録される"""
        initial_count = AuditLog.query.count()
        
        # ログイン処理をシミュレート
        log_audit('login', target_type='user', target_id=test_user.id, 
                 metadata_dict={'username': test_user.username}, user_id=test_user.id)
        
        assert AuditLog.query.count() == initial_count + 1
        
        log = AuditLog.query.filter_by(action='login').order_by(AuditLog.id.desc()).first()
        assert log is not None
        assert log.target_type == 'user'
    
    def test_audit_log_on_clock_in(self, client, test_user):
        """出勤時に監査ログが記録される"""
        from app import Shift
        now = datetime.now(timezone.utc)
        shift = Shift(user_id=test_user.id, clock_in_at=now)
        db.session.add(shift)
        db.session.commit()
        
        log_audit('clock_in', target_type='shift', target_id=shift.id,
                 metadata_dict={'at': shift.clock_in_at.isoformat()}, user_id=test_user.id)
        
        log = AuditLog.query.filter_by(action='clock_in').order_by(AuditLog.id.desc()).first()
        assert log is not None
        assert log.target_type == 'shift'
        assert log.target_id == shift.id
    
    def test_audit_log_limit(self, client, logged_in_admin, test_user):
        """監査ログの件数制限"""
        # 複数のログを作成
        for i in range(10):
            log_audit(f'action_{i}', user_id=test_user.id)
        
        response = client.get('/admin/audit?limit=5')
        assert response.status_code == 200

