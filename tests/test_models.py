"""
データベースモデルのテスト
"""
import pytest
from datetime import datetime, timezone, timedelta
from app import User, Shift, Break, AuditLog, db

class TestUserModel:
    """Userモデルのテスト"""
    
    def test_user_creation(self, client):
        """ユーザー作成のテスト"""
        user = User(
            username='newuser',
            email='newuser@example.com',
            name='新規ユーザー',
            role='user'
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        
        assert user.id is not None
        assert user.username == 'newuser'
        assert user.email == 'newuser@example.com'
        assert user.role == 'user'
        assert user.check_password('password123')
        assert not user.check_password('wrongpassword')
    
    def test_user_password_hashing(self, client):
        """パスワードハッシュ化のテスト"""
        user = User(username='test', role='user')
        user.set_password('mypassword')
        
        assert user.password_hash != 'mypassword'
        assert user.check_password('mypassword')
        assert not user.check_password('wrongpassword')
    
    def test_user_is_admin(self, client):
        """管理者判定のテスト"""
        admin = User(username='admin', role='admin')
        user = User(username='user', role='user')
        
        assert admin.is_admin() is True
        assert user.is_admin() is False
    
    def test_user_unique_username(self, client):
        """ユーザー名の一意性テスト"""
        user1 = User(username='unique', role='user')
        user1.set_password('pass')
        db.session.add(user1)
        db.session.commit()
        
        user2 = User(username='unique', role='user')
        user2.set_password('pass')
        db.session.add(user2)
        
        with pytest.raises(Exception):
            db.session.commit()
        
        db.session.rollback()
    
    def test_user_relationship_with_shifts(self, client, test_user):
        """ユーザーとシフトのリレーションシップテスト"""
        shift = Shift(
            user_id=test_user.id,
            clock_in_at=datetime.now(timezone.utc)
        )
        db.session.add(shift)
        db.session.commit()
        
        assert len(test_user.shifts) == 1
        assert test_user.shifts[0].id == shift.id

class TestShiftModel:
    """Shiftモデルのテスト"""
    
    def test_shift_creation(self, client, test_user):
        """シフト作成のテスト"""
        now = datetime.now(timezone.utc)
        shift = Shift(
            user_id=test_user.id,
            clock_in_at=now,
            clock_in_ip='127.0.0.1',
            clock_in_ua='Test Agent'
        )
        db.session.add(shift)
        db.session.commit()
        
        assert shift.id is not None
        assert shift.user_id == test_user.id
        assert shift.is_open is True
    
    def test_shift_is_open(self, client, test_user):
        """is_openプロパティのテスト"""
        now = datetime.now(timezone.utc)
        
        open_shift = Shift(
            user_id=test_user.id,
            clock_in_at=now
        )
        closed_shift = Shift(
            user_id=test_user.id,
            clock_in_at=now - timedelta(hours=8),
            clock_out_at=now
        )
        
        assert open_shift.is_open is True
        assert closed_shift.is_open is False
    
    def test_shift_total_break_seconds(self, client, open_shift):
        """休憩時間合計の計算テスト"""
        now = datetime.now(timezone.utc)
        
        # 休憩1: 30分
        break1 = Break(
            shift_id=open_shift.id,
            start_at=now - timedelta(hours=2, minutes=30),
            end_at=now - timedelta(hours=2)
        )
        # 休憩2: 15分（未終了）
        break2 = Break(
            shift_id=open_shift.id,
            start_at=now - timedelta(minutes=15),
            end_at=None
        )
        db.session.add_all([break1, break2])
        db.session.commit()
        
        total = open_shift.total_break_seconds(now=now)
        assert total == (30 * 60) + (15 * 60)  # 45分 = 2700秒
    
    def test_shift_worked_seconds(self, client, test_user):
        """実働時間の計算テスト"""
        now = datetime.now(timezone.utc)
        
        # 8時間出勤、1時間休憩 = 7時間実働
        shift = Shift(
            user_id=test_user.id,
            clock_in_at=now - timedelta(hours=8),
            clock_out_at=now
        )
        db.session.add(shift)
        db.session.commit()  # 先にshiftをコミット
        
        break_record = Break(
            shift_id=shift.id,
            start_at=now - timedelta(hours=4),
            end_at=now - timedelta(hours=3)
        )
        db.session.add(break_record)
        db.session.commit()
        
        worked = shift.worked_seconds()
        assert worked == 7 * 3600  # 7時間 = 25200秒
    
    def test_shift_cascade_delete(self, client, test_user):
        """ユーザー削除時のカスケード削除テスト"""
        shift = Shift(
            user_id=test_user.id,
            clock_in_at=datetime.now(timezone.utc)
        )
        db.session.add(shift)
        db.session.commit()
        shift_id = shift.id
        
        db.session.delete(test_user)
        db.session.commit()
        
        # クエリで確認（セッションをリフレッシュ）
        db.session.expunge_all()
        result = Shift.query.filter_by(id=shift_id).first()
        assert result is None

class TestBreakModel:
    """Breakモデルのテスト"""
    
    def test_break_creation(self, client, open_shift):
        """休憩作成のテスト"""
        now = datetime.now(timezone.utc)
        break_record = Break(
            shift_id=open_shift.id,
            start_at=now,
            start_ip='127.0.0.1',
            start_ua='Test Agent'
        )
        db.session.add(break_record)
        db.session.commit()
        
        assert break_record.id is not None
        assert break_record.shift_id == open_shift.id
    
    def test_break_cascade_delete(self, client, open_shift):
        """シフト削除時のカスケード削除テスト"""
        break_record = Break(
            shift_id=open_shift.id,
            start_at=datetime.now(timezone.utc)
        )
        db.session.add(break_record)
        db.session.commit()
        break_id = break_record.id
        
        db.session.delete(open_shift)
        db.session.commit()
        
        # クエリで確認（セッションをリフレッシュ）
        db.session.expunge_all()
        result = Break.query.filter_by(id=break_id).first()
        assert result is None

class TestAuditLogModel:
    """AuditLogモデルのテスト"""
    
    def test_audit_log_creation(self, client, test_user):
        """監査ログ作成のテスト"""
        log = AuditLog(
            user_id=test_user.id,
            action='test_action',
            target_type='test_target',
            target_id=1,
            ip='127.0.0.1',
            user_agent='Test Agent',
            metadata_json='{"key": "value"}',
            signature='test_signature'
        )
        db.session.add(log)
        db.session.commit()
        
        assert log.id is not None
        assert log.user_id == test_user.id
        assert log.action == 'test_action'
    
    def test_audit_log_without_user(self, client):
        """ユーザーなしの監査ログ作成テスト"""
        log = AuditLog(
            action='system_action',
            target_type='system',
            ip='127.0.0.1'
        )
        db.session.add(log)
        db.session.commit()
        
        assert log.id is not None
        assert log.user_id is None

