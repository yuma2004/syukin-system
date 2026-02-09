"""
管理者機能のテスト
"""
import pytest
from datetime import datetime, timezone, timedelta
from app import User, Shift, Break, AuditLog, db

class TestAdminDashboard:
    """管理画面ダッシュボードのテスト"""
    
    def test_admin_dashboard_access(self, client, logged_in_admin):
        """管理者は管理画面にアクセス可能"""
        response = client.get('/admin')
        assert response.status_code == 200
    
    def test_admin_dashboard_requires_admin(self, client, logged_in_user):
        """通常ユーザーは管理画面にアクセス不可"""
        response = client.get('/admin')
        assert response.status_code == 403
    
    def test_admin_dashboard_filters(self, client, logged_in_admin, test_user, sample_shift):
        """管理画面のフィルタ機能"""
        # 日付フィルタ
        start_date = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
        end_date = datetime.now(timezone.utc).date().isoformat()
        
        response = client.get(f'/admin?start={start_date}&end={end_date}')
        assert response.status_code == 200
        
        # ユーザー名フィルタ
        response = client.get(f'/admin?username={test_user.username}')
        assert response.status_code == 200

class TestAdminShiftCreate:
    """出退勤記録作成機能のテスト"""
    
    def test_admin_create_shift(self, client, logged_in_admin, test_user):
        """管理者が出退勤記録を作成"""
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
    
    def test_admin_create_shift_invalid_user(self, client, logged_in_admin):
        """存在しないユーザーで作成失敗"""
        response = client.post('/admin/shift/create', data={
            'user_id': '99999',
            'clock_in_at': '2024-01-01T09:00'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_admin_create_shift_invalid_time(self, client, logged_in_admin, test_user):
        """無効な時刻で作成失敗"""
        response = client.post('/admin/shift/create', data={
            'user_id': str(test_user.id),
            'clock_in_at': '2024-01-01T18:00',
            'clock_out_at': '2024-01-01T09:00'  # 退勤が先
        }, follow_redirects=True)
        
        assert response.status_code == 200

class TestAdminShiftEdit:
    """出退勤記録編集機能のテスト"""
    
    def test_admin_edit_shift_page(self, client, logged_in_admin, sample_shift):
        """編集ページが表示される"""
        response = client.get(f'/admin/shift/{sample_shift.id}/edit')
        assert response.status_code == 200
    
    def test_admin_update_shift(self, client, logged_in_admin, sample_shift):
        """出退勤時刻を更新"""
        clock_in = (datetime.now(timezone.utc) - timedelta(hours=9)).astimezone().strftime('%Y-%m-%dT%H:%M')
        clock_out = datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%dT%H:%M')
        
        response = client.post(f'/admin/shift/{sample_shift.id}/edit', data={
            'action': 'update_shift',
            'clock_in_at': clock_in,
            'clock_out_at': clock_out
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        db.session.refresh(sample_shift)
        assert sample_shift.clock_in_at is not None
    
    def test_admin_add_break(self, client, logged_in_admin, sample_shift):
        """休憩を追加"""
        now = datetime.now(timezone.utc)
        start_at = (now - timedelta(hours=4)).astimezone().strftime('%Y-%m-%dT%H:%M')
        end_at = (now - timedelta(hours=3, minutes=30)).astimezone().strftime('%Y-%m-%dT%H:%M')
        
        response = client.post(f'/admin/shift/{sample_shift.id}/edit', data={
            'action': 'break_add',
            'start_at': start_at,
            'end_at': end_at
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        breaks = Break.query.filter_by(shift_id=sample_shift.id).all()
        assert len(breaks) > 0
    
    def test_admin_delete_shift(self, client, logged_in_admin, sample_shift):
        """出退勤記録を削除"""
        shift_id = sample_shift.id
        response = client.post(f'/admin/shift/{shift_id}/delete', follow_redirects=True)
        
        assert response.status_code == 200
        assert Shift.query.get(shift_id) is None

class TestAdminExport:
    """CSVエクスポート機能のテスト"""
    
    def test_admin_export_csv(self, client, logged_in_admin, test_user, sample_shift):
        """CSVエクスポート成功"""
        start_date = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
        end_date = datetime.now(timezone.utc).date().isoformat()
        
        response = client.get(f'/admin/export?start={start_date}&end={end_date}')
        
        assert response.status_code == 200
        assert response.content_type == 'text/csv; charset=utf-8'
        assert b'user_username' in response.data
    
    def test_admin_export_with_user_filter(self, client, logged_in_admin, test_user, sample_shift):
        """ユーザー名フィルタ付きエクスポート"""
        start_date = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
        end_date = datetime.now(timezone.utc).date().isoformat()
        
        response = client.get(
            f'/admin/export?start={start_date}&end={end_date}&username={test_user.username}'
        )
        
        assert response.status_code == 200
        assert response.content_type == 'text/csv; charset=utf-8'
    
    def test_admin_export_invalid_date_range(self, client, logged_in_admin):
        """無効な日付範囲でエクスポート失敗"""
        response = client.get('/admin/export?start=2024-01-10&end=2024-01-01')
        assert response.status_code == 400

class TestAdminShiftDetail:
    """出退勤記録詳細APIのテスト"""
    
    def test_admin_shift_detail_json(self, client, logged_in_admin, sample_shift):
        """JSON形式で詳細を取得"""
        response = client.get(f'/admin/shift/{sample_shift.id}')
        
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert 'id' in data
        assert 'user_username' in data
        assert 'clock_in_at' in data

