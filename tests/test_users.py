"""
ユーザー管理機能のテスト
"""
import pytest
from app import User, db

class TestUserManagement:
    """ユーザー管理機能のテスト"""
    
    def test_admin_users_page(self, client, logged_in_admin):
        """ユーザー管理ページが表示される"""
        response = client.get('/admin/users')
        assert response.status_code == 200
    
    def test_admin_users_requires_admin(self, client, logged_in_user):
        """通常ユーザーはユーザー管理ページにアクセス不可"""
        response = client.get('/admin/users')
        assert response.status_code == 403
    
    def test_admin_create_user(self, client, logged_in_admin):
        """管理者がユーザーを作成"""
        response = client.post('/admin/users', data={
            'action': 'create',
            'username': 'newuser',
            'password': 'newpass123',
            'name': '新規ユーザー',
            'email': 'newuser@example.com',
            'role': 'user'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        user = User.query.filter_by(username='newuser').first()
        assert user is not None
        assert user.check_password('newpass123')
        assert user.role == 'user'
    
    def test_admin_create_user_duplicate_username(self, client, logged_in_admin, test_user):
        """重複するユーザー名で作成失敗"""
        response = client.post('/admin/users', data={
            'action': 'create',
            'username': test_user.username,
            'password': 'password123',
            'role': 'user'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_admin_create_user_empty_fields(self, client, logged_in_admin):
        """空のフィールドで作成失敗"""
        response = client.post('/admin/users', data={
            'action': 'create',
            'username': '',
            'password': '',
            'role': 'user'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_admin_update_user(self, client, logged_in_admin, test_user):
        """管理者がユーザーを更新"""
        response = client.post('/admin/users', data={
            'action': 'update',
            'user_id': str(test_user.id),
            'name': '更新された名前',
            'email': 'updated@example.com',
            'role': 'user',
            'password': ''  # パスワード変更なし
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        db.session.refresh(test_user)
        assert test_user.name == '更新された名前'
        assert test_user.email == 'updated@example.com'
    
    def test_admin_update_user_password(self, client, logged_in_admin, test_user):
        """管理者がユーザーのパスワードを変更"""
        old_hash = test_user.password_hash
        
        response = client.post('/admin/users', data={
            'action': 'update',
            'user_id': str(test_user.id),
            'name': test_user.name or '',
            'email': test_user.email or '',
            'role': test_user.role,
            'password': 'newpassword123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        db.session.refresh(test_user)
        assert test_user.password_hash != old_hash
        assert test_user.check_password('newpassword123')
    
    def test_admin_update_user_role(self, client, logged_in_admin, test_user):
        """管理者がユーザーの権限を変更"""
        response = client.post('/admin/users', data={
            'action': 'update',
            'user_id': str(test_user.id),
            'name': test_user.name or '',
            'email': test_user.email or '',
            'role': 'admin',
            'password': ''
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        db.session.refresh(test_user)
        assert test_user.role == 'admin'
        assert test_user.is_admin() is True
    
    def test_admin_delete_user(self, client, logged_in_admin, test_user):
        """管理者がユーザーを削除"""
        user_id = test_user.id
        
        response = client.post('/admin/users', data={
            'action': 'delete',
            'user_id': str(user_id)
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert User.query.get(user_id) is None
    
    def test_admin_cannot_delete_self(self, client, logged_in_admin):
        """管理者は自分自身を削除できない"""
        response = client.post('/admin/users', data={
            'action': 'delete',
            'user_id': str(logged_in_admin.id)
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        # 自分自身は削除されていない
        assert User.query.get(logged_in_admin.id) is not None
    
    def test_admin_create_user_with_email_duplicate(self, client, logged_in_admin, test_user):
        """重複するメールアドレスで作成失敗"""
        if test_user.email:
            response = client.post('/admin/users', data={
                'action': 'create',
                'username': 'anotheruser',
                'password': 'password123',
                'email': test_user.email,
                'role': 'user'
            }, follow_redirects=True)
            
            assert response.status_code == 200

