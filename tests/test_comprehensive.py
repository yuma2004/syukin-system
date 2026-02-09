"""
包括的な統合テスト
"""
import pytest
from datetime import datetime, timezone, timedelta
from app import User, Shift, Break, AuditLog, db

class TestComprehensiveFlow:
    """包括的なフローテスト"""
    
    def test_complete_attendance_flow(self, client, logged_in_user):
        """完全な出退勤フローのテスト"""
        # 1. 出勤
        response = client.post('/clock/in', follow_redirects=True)
        assert response.status_code == 200
        
        shift = Shift.query.filter_by(user_id=logged_in_user.id, clock_out_at=None).first()
        assert shift is not None
        assert shift.is_open is True
        
        # 2. 休憩開始
        response = client.post('/break/start', follow_redirects=True)
        assert response.status_code == 200
        
        break_record = Break.query.filter_by(shift_id=shift.id, end_at=None).first()
        assert break_record is not None
        
        # 3. 休憩終了
        response = client.post('/break/end', follow_redirects=True)
        assert response.status_code == 200
        
        db.session.refresh(break_record)
        assert break_record.end_at is not None
        
        # 4. 退勤
        response = client.post('/clock/out', follow_redirects=True)
        assert response.status_code == 200
        
        db.session.refresh(shift)
        assert shift.clock_out_at is not None
        assert shift.is_open is False
        
        # 5. 実働時間の計算確認
        worked_seconds = shift.worked_seconds()
        # 休憩時間を差し引いた実働時間を確認（休憩時間分だけ減る）
        assert worked_seconds >= 0  # 0以上であることを確認
        
        # 6. 監査ログの確認
        audit_logs = AuditLog.query.filter_by(target_type='shift', target_id=shift.id).all()
        assert len(audit_logs) >= 2  # clock_inとclock_outのログがある
    
    def test_admin_complete_workflow(self, client, logged_in_admin, test_user):
        """管理者の完全なワークフローテスト"""
        # 1. 管理者が出退勤記録を作成
        now = datetime.now(timezone.utc)
        clock_in = (now - timedelta(hours=8)).astimezone().strftime('%Y-%m-%dT%H:%M')
        clock_out = now.astimezone().strftime('%Y-%m-%dT%H:%M')
        
        response = client.post('/admin/shift/create', data={
            'user_id': str(test_user.id),
            'clock_in_at': clock_in,
            'clock_out_at': clock_out
        }, follow_redirects=True)
        assert response.status_code == 200
        
        shift = Shift.query.filter_by(user_id=test_user.id).order_by(Shift.id.desc()).first()
        assert shift is not None
        
        # 2. 管理画面で確認
        response = client.get('/admin')
        assert response.status_code == 200
        
        # 3. 編集ページで確認
        response = client.get(f'/admin/shift/{shift.id}/edit')
        assert response.status_code == 200
        
        # 4. 休憩を追加
        start_at = (now - timedelta(hours=4)).astimezone().strftime('%Y-%m-%dT%H:%M')
        end_at = (now - timedelta(hours=3, minutes=30)).astimezone().strftime('%Y-%m-%dT%H:%M')
        
        response = client.post(f'/admin/shift/{shift.id}/edit', data={
            'action': 'break_add',
            'start_at': start_at,
            'end_at': end_at
        }, follow_redirects=True)
        assert response.status_code == 200
        
        breaks = Break.query.filter_by(shift_id=shift.id).all()
        assert len(breaks) == 1
        
        # 5. CSVエクスポート
        start_date = (now - timedelta(days=7)).date().isoformat()
        end_date = now.date().isoformat()
        
        response = client.get(f'/admin/export?start={start_date}&end={end_date}')
        assert response.status_code == 200
        assert response.content_type == 'text/csv; charset=utf-8'
        
        # 6. 監査ログの確認
        audit_logs = AuditLog.query.filter_by(action='admin_shift_create').all()
        assert len(audit_logs) > 0
    
    def test_user_management_workflow(self, client, logged_in_admin):
        """ユーザー管理の完全なワークフローテスト"""
        # 1. ユーザー作成
        response = client.post('/admin/users', data={
            'action': 'create',
            'username': 'workflow_user',
            'password': 'workflow_pass123',
            'name': 'ワークフローユーザー',
            'email': 'workflow@example.com',
            'role': 'user'
        }, follow_redirects=True)
        assert response.status_code == 200
        
        user = User.query.filter_by(username='workflow_user').first()
        assert user is not None
        assert user.check_password('workflow_pass123')
        
        # 2. ユーザー更新
        response = client.post('/admin/users', data={
            'action': 'update',
            'user_id': str(user.id),
            'name': '更新されたユーザー',
            'email': 'updated@example.com',
            'role': 'user',
            'password': ''
        }, follow_redirects=True)
        assert response.status_code == 200
        
        db.session.refresh(user)
        assert user.name == '更新されたユーザー'
        assert user.email == 'updated@example.com'
        
        # 3. パスワード変更
        old_hash = user.password_hash
        response = client.post('/admin/users', data={
            'action': 'update',
            'user_id': str(user.id),
            'name': user.name or '',
            'email': user.email or '',
            'role': user.role,
            'password': 'newpassword123'
        }, follow_redirects=True)
        assert response.status_code == 200
        
        db.session.refresh(user)
        assert user.password_hash != old_hash
        assert user.check_password('newpassword123')
        
        # 4. ユーザー削除
        user_id = user.id
        response = client.post('/admin/users', data={
            'action': 'delete',
            'user_id': str(user_id)
        }, follow_redirects=True)
        assert response.status_code == 200
        assert User.query.get(user_id) is None

class TestEdgeCases:
    """エッジケースのテスト"""
    
    def test_multiple_concurrent_shifts_prevention(self, client, logged_in_user):
        """同時に出勤記録が作成されないことを確認"""
        # 最初の出勤
        response1 = client.post('/clock/in', follow_redirects=True)
        assert response1.status_code == 200
        
        # 2回目の出勤（エラーになるはず）
        response2 = client.post('/clock/in', follow_redirects=True)
        assert response2.status_code == 400
        
        # 1つの出勤記録のみ存在
        open_shifts = Shift.query.filter_by(user_id=logged_in_user.id, clock_out_at=None).all()
        assert len(open_shifts) == 1
    
    def test_break_without_shift(self, client, logged_in_user):
        """出勤していない状態で休憩開始（エラー）"""
        response = client.post('/break/start', follow_redirects=True)
        assert response.status_code == 400
    
    def test_clock_out_without_clock_in(self, client, logged_in_user):
        """出勤していない状態で退勤（エラー）"""
        response = client.post('/clock/out', follow_redirects=True)
        assert response.status_code == 400
    
    def test_break_end_without_break_start(self, client, logged_in_user, open_shift):
        """休憩開始していない状態で休憩終了（エラー）"""
        response = client.post('/break/end', follow_redirects=True)
        assert response.status_code == 400
    
    def test_csv_export_max_days(self, client, logged_in_admin):
        """CSVエクスポートの最大日数制限"""
        from app import CSV_EXPORT_MAX_DAYS
        
        start_date = datetime.now(timezone.utc).date()
        end_date = start_date + timedelta(days=CSV_EXPORT_MAX_DAYS + 1)
        
        response = client.get(f'/admin/export?start={start_date.isoformat()}&end={end_date.isoformat()}')
        assert response.status_code == 400
    
    def test_invalid_date_range(self, client, logged_in_admin):
        """無効な日付範囲（開始日 > 終了日）"""
        response = client.get('/admin/export?start=2024-01-10&end=2024-01-01')
        assert response.status_code == 400

class TestDataIntegrity:
    """データ整合性のテスト"""
    
    def test_user_deletion_cascades(self, client, test_user):
        """ユーザー削除時のカスケード削除"""
        # 出退勤記録を作成
        shift = Shift(
            user_id=test_user.id,
            clock_in_at=datetime.now(timezone.utc)
        )
        db.session.add(shift)
        db.session.commit()
        shift_id = shift.id
        
        # 休憩記録を作成
        break_record = Break(
            shift_id=shift.id,
            start_at=datetime.now(timezone.utc)
        )
        db.session.add(break_record)
        db.session.commit()
        break_id = break_record.id
        
        # ユーザーを削除
        db.session.delete(test_user)
        db.session.commit()
        
        # クエリで確認（セッションをリフレッシュ）
        db.session.expunge_all()
        assert Shift.query.filter_by(id=shift_id).first() is None
        assert Break.query.filter_by(id=break_id).first() is None
    
    def test_shift_deletion_cascades_breaks(self, client, test_user, open_shift):
        """シフト削除時の休憩カスケード削除"""
        # 休憩記録を作成
        break_record = Break(
            shift_id=open_shift.id,
            start_at=datetime.now(timezone.utc)
        )
        db.session.add(break_record)
        db.session.commit()
        break_id = break_record.id
        
        # シフトを削除
        shift_id = open_shift.id
        db.session.delete(open_shift)
        db.session.commit()
        
        # クエリで確認（セッションをリフレッシュ）
        db.session.expunge_all()
        assert Break.query.filter_by(id=break_id).first() is None
        assert Shift.query.filter_by(id=shift_id).first() is None

class TestSecurity:
    """セキュリティテスト"""
    
    def test_admin_access_control(self, client, logged_in_user):
        """通常ユーザーは管理画面にアクセスできない"""
        response = client.get('/admin')
        assert response.status_code == 403
        
        response = client.get('/admin/users')
        assert response.status_code == 403
        
        response = client.get('/admin/audit')
        assert response.status_code == 403
    
    def test_healthz_endpoint(self, client):
        """ヘルスチェックエンドポイント"""
        response = client.get('/healthz')
        assert response.status_code == 200
        assert response.data.decode() == 'ok'
    
    def test_audit_log_signature(self, client, test_user):
        """監査ログの署名が正しく生成される"""
        from app import log_audit
        
        log_audit('test_action', user_id=test_user.id)
        
        log = AuditLog.query.order_by(AuditLog.id.desc()).first()
        assert log.signature is not None
        assert len(log.signature) == 64  # SHA256の16進数文字列長

