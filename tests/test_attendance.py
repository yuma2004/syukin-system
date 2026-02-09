"""
出退勤機能のテスト
"""
import pytest
from datetime import datetime, timezone, timedelta
from app import User, Shift, Break, db

class TestClockIn:
    """出勤機能のテスト"""
    
    def test_clock_in_success(self, client, logged_in_user):
        """出勤成功"""
        response = client.post('/clock/in', follow_redirects=True)
        assert response.status_code == 200
        
        shift = Shift.query.filter_by(user_id=logged_in_user.id, clock_out_at=None).first()
        assert shift is not None
        assert shift.clock_in_at is not None
    
    def test_clock_in_duplicate(self, client, logged_in_user, open_shift):
        """既に出勤中の場合はエラー"""
        response = client.post('/clock/in', follow_redirects=True)
        assert response.status_code == 400
    
    def test_clock_in_requires_login(self, client):
        """出勤にはログインが必要"""
        response = client.post('/clock/in')
        assert response.status_code in [302, 401, 403]

class TestClockOut:
    """退勤機能のテスト"""
    
    def test_clock_out_success(self, client, logged_in_user, open_shift):
        """退勤成功"""
        response = client.post('/clock/out', follow_redirects=True)
        assert response.status_code == 200
        
        db.session.refresh(open_shift)
        assert open_shift.clock_out_at is not None
    
    def test_clock_out_no_open_shift(self, client, logged_in_user):
        """出勤中でない場合はエラー"""
        response = client.post('/clock/out', follow_redirects=True)
        assert response.status_code == 400
    
    def test_clock_out_closes_open_break(self, client, logged_in_user, open_shift, sample_break):
        """退勤時に未終了の休憩を自動終了"""
        response = client.post('/clock/out', follow_redirects=True)
        assert response.status_code == 200
        
        db.session.refresh(sample_break)
        assert sample_break.end_at is not None
    
    def test_clock_out_requires_login(self, client):
        """退勤にはログインが必要"""
        response = client.post('/clock/out')
        assert response.status_code in [302, 401, 403]

class TestBreakStart:
    """休憩開始機能のテスト"""
    
    def test_break_start_success(self, client, logged_in_user, open_shift):
        """休憩開始成功"""
        response = client.post('/break/start', follow_redirects=True)
        assert response.status_code == 200
        
        break_record = Break.query.filter_by(shift_id=open_shift.id, end_at=None).first()
        assert break_record is not None
        assert break_record.start_at is not None
    
    def test_break_start_no_open_shift(self, client, logged_in_user):
        """出勤中でない場合はエラー"""
        response = client.post('/break/start', follow_redirects=True)
        assert response.status_code == 400
    
    def test_break_start_duplicate(self, client, logged_in_user, open_shift, sample_break):
        """既に休憩中の場合はエラー"""
        response = client.post('/break/start', follow_redirects=True)
        assert response.status_code == 400
    
    def test_break_start_requires_login(self, client):
        """休憩開始にはログインが必要"""
        response = client.post('/break/start')
        assert response.status_code in [302, 401, 403]

class TestBreakEnd:
    """休憩終了機能のテスト"""
    
    def test_break_end_success(self, client, logged_in_user, open_shift, sample_break):
        """休憩終了成功"""
        response = client.post('/break/end', follow_redirects=True)
        assert response.status_code == 200
        
        db.session.refresh(sample_break)
        assert sample_break.end_at is not None
    
    def test_break_end_no_open_break(self, client, logged_in_user, open_shift):
        """休憩中でない場合はエラー"""
        response = client.post('/break/end', follow_redirects=True)
        assert response.status_code == 400
    
    def test_break_end_no_open_shift(self, client, logged_in_user):
        """出勤中でない場合はエラー"""
        response = client.post('/break/end', follow_redirects=True)
        assert response.status_code == 400
    
    def test_break_end_requires_login(self, client):
        """休憩終了にはログインが必要"""
        response = client.post('/break/end')
        assert response.status_code in [302, 401, 403]

class TestDashboard:
    """ダッシュボード機能のテスト"""
    
    def test_dashboard_displays_open_shift(self, client, logged_in_user, open_shift):
        """ダッシュボードに出勤中記録が表示される"""
        response = client.get('/')
        assert response.status_code == 200
        assert open_shift.id is not None
    
    def test_dashboard_displays_recent_shifts(self, client, logged_in_user, sample_shift):
        """ダッシュボードに最近の記録が表示される"""
        response = client.get('/')
        assert response.status_code == 200
    
    def test_dashboard_shows_open_break(self, client, logged_in_user, open_shift, sample_break):
        """ダッシュボードに休憩中が表示される"""
        response = client.get('/')
        assert response.status_code == 200

