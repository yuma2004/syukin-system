import json

from sqlalchemy.exc import IntegrityError

from app import AuditLog, User, db


def test_未ログインでユーザー管理画面にアクセスするとログイン画面へリダイレクトされる(client):
    """未ログインでユーザー管理画面にアクセスするとログイン画面へリダイレクトされる。"""
    response = client.get("/admin/users", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_一般ユーザーはユーザー管理画面にアクセスできず403になる(client, login_as):
    """一般ユーザーはユーザー管理画面にアクセスできず403になる。"""
    login_as(username="member-get", password="member-pass", role="user")

    response = client.get("/admin/users", follow_redirects=False)

    assert response.status_code == 403


def test_一般ユーザーはユーザー管理post操作を実行できず403になる(client, login_as):
    """一般ユーザーはユーザー管理POST操作を実行できず403になる。"""
    login_as(username="member-post", password="member-pass", role="user")

    response = client.post("/admin/users", data={"action": "create"}, follow_redirects=False)

    assert response.status_code == 403


def test_管理者でもcsrfトークンなしのユーザー管理postは400になる(client, login_as_admin):
    """管理者でもCSRFトークンなしのユーザー管理POSTは400になる。"""
    login_as_admin(username="admin-no-csrf", password="admin-pass")

    response = client.post(
        "/admin/users",
        data={"action": "create", "username": "new-user", "password": "pass12345"},
        follow_redirects=False,
    )

    assert response.status_code == 400


def test_管理者はユーザーを作成でき監査ログが残る(
    client,
    login_as_admin,
    set_csrf_token,
    list_audit_logs,
    app,
):
    """管理者はユーザーを作成でき監査ログが残る。"""
    login_as_admin(username="admin-create", password="admin-pass")
    token = set_csrf_token(client)

    response = client.post(
        "/admin/users",
        data={
            "csrf_token": token,
            "action": "create",
            "username": "created-user",
            "password": "created-pass",
            "name": "作成ユーザー",
            "email": "created@example.com",
            "role": "user",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/admin/users" in response.headers["Location"]

    with app.app_context():
        created = User.query.filter_by(username="created-user").first()
        assert created is not None
        assert created.email == "created@example.com"
        assert created.check_password("created-pass")

    logs = list_audit_logs(action="admin_user_create")
    assert len(logs) == 1
    metadata = json.loads(logs[0].metadata_json)
    assert metadata["username"] == "created-user"
    assert metadata["role"] == "user"


def test_ユーザー作成でユーザーid未入力だと作成されない(
    client,
    login_as_admin,
    set_csrf_token,
    app,
    list_audit_logs,
):
    """ユーザー作成でユーザーID未入力だと作成されない。"""
    login_as_admin(username="admin-missing-username", password="admin-pass")
    token = set_csrf_token(client)

    response = client.post(
        "/admin/users",
        data={
            "csrf_token": token,
            "action": "create",
            "username": "",
            "password": "created-pass",
            "email": "missing-username@example.com",
            "role": "user",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        assert User.query.filter_by(email="missing-username@example.com").first() is None
    assert list_audit_logs(action="admin_user_create") == []


def test_ユーザー作成でパスワード未入力だと作成されない(
    client,
    login_as_admin,
    set_csrf_token,
    app,
    list_audit_logs,
):
    """ユーザー作成でパスワード未入力だと作成されない。"""
    login_as_admin(username="admin-missing-password", password="admin-pass")
    token = set_csrf_token(client)

    response = client.post(
        "/admin/users",
        data={
            "csrf_token": token,
            "action": "create",
            "username": "missing-password-user",
            "password": "",
            "email": "missing-password@example.com",
            "role": "user",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        assert User.query.filter_by(username="missing-password-user").first() is None
    assert list_audit_logs(action="admin_user_create") == []


def test_ユーザー作成で重複ユーザーidは作成されない(
    client,
    login_as_admin,
    set_csrf_token,
    create_user,
    app,
    list_audit_logs,
):
    """ユーザー作成で重複ユーザーIDは作成されない。"""
    login_as_admin(username="admin-dup-username", password="admin-pass")
    create_user(username="duplicate-user", password="existing-pass")
    token = set_csrf_token(client)

    response = client.post(
        "/admin/users",
        data={
            "csrf_token": token,
            "action": "create",
            "username": "duplicate-user",
            "password": "new-pass",
            "email": "new-dup-user@example.com",
            "role": "user",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        assert User.query.filter_by(username="duplicate-user").count() == 1
    assert list_audit_logs(action="admin_user_create") == []


def test_ユーザー作成で重複メールアドレスは作成されない(
    client,
    login_as_admin,
    set_csrf_token,
    create_user,
    app,
    list_audit_logs,
):
    """ユーザー作成で重複メールアドレスは作成されない。"""
    login_as_admin(username="admin-dup-email", password="admin-pass")
    create_user(username="existing-email-user", password="existing-pass", email="dup@example.com")
    token = set_csrf_token(client)

    response = client.post(
        "/admin/users",
        data={
            "csrf_token": token,
            "action": "create",
            "username": "new-email-user",
            "password": "new-pass",
            "email": "dup@example.com",
            "role": "user",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        assert User.query.filter_by(email="dup@example.com").count() == 1
        assert User.query.filter_by(username="new-email-user").first() is None
    assert list_audit_logs(action="admin_user_create") == []


def test_ユーザー作成でdbコミット失敗時はロールバックされる(
    client,
    login_as_admin,
    set_csrf_token,
    monkeypatch,
    app,
    list_audit_logs,
):
    """ユーザー作成でDBコミット失敗時はロールバックされる。"""
    login_as_admin(username="admin-create-rollback", password="admin-pass")
    token = set_csrf_token(client)

    def _raise_integrity_error():
        raise IntegrityError("forced", {}, Exception("forced"))

    monkeypatch.setattr(db.session, "commit", _raise_integrity_error)

    response = client.post(
        "/admin/users",
        data={
            "csrf_token": token,
            "action": "create",
            "username": "rollback-user",
            "password": "rollback-pass",
            "email": "rollback@example.com",
            "role": "user",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        assert User.query.filter_by(username="rollback-user").first() is None
    assert list_audit_logs(action="admin_user_create") == []


def test_ユーザー更新でパスワード空なら既存パスワードを維持して更新できる(
    client,
    login_as_admin,
    set_csrf_token,
    create_user,
    app,
    list_audit_logs,
):
    """ユーザー更新でパスワード空なら既存パスワードを維持して更新できる。"""
    login_as_admin(username="admin-update-no-password", password="admin-pass")
    target_user_id = create_user(
        username="update-target-a",
        password="before-pass",
        name="更新前",
        email="before@example.com",
        role="user",
    )
    token = set_csrf_token(client)
    with app.app_context():
        before = db.session.get(User, target_user_id)
        before_hash = before.password_hash

    response = client.post(
        "/admin/users",
        data={
            "csrf_token": token,
            "action": "update",
            "user_id": str(target_user_id),
            "name": "更新後",
            "email": "after@example.com",
            "role": "admin",
            "password": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        updated = db.session.get(User, target_user_id)
        assert updated.name == "更新後"
        assert updated.email == "after@example.com"
        assert updated.role == "admin"
        assert updated.password_hash == before_hash
        assert updated.check_password("before-pass")

    logs = list_audit_logs(action="admin_user_update")
    assert len(logs) == 1
    metadata = json.loads(logs[0].metadata_json)
    assert metadata["username"] == "update-target-a"
    assert metadata["role"] == "admin"
    assert metadata["password_changed"] is False


def test_ユーザー更新で新パスワード入力時はパスワードが更新される(
    client,
    login_as_admin,
    set_csrf_token,
    create_user,
    app,
    list_audit_logs,
):
    """ユーザー更新で新パスワード入力時はパスワードが更新される。"""
    login_as_admin(username="admin-update-password", password="admin-pass")
    target_user_id = create_user(
        username="update-target-b",
        password="before-pass",
        email="before-b@example.com",
        role="user",
    )
    token = set_csrf_token(client)
    with app.app_context():
        before = db.session.get(User, target_user_id)
        before_hash = before.password_hash

    response = client.post(
        "/admin/users",
        data={
            "csrf_token": token,
            "action": "update",
            "user_id": str(target_user_id),
            "name": "更新後B",
            "email": "after-b@example.com",
            "role": "user",
            "password": "after-pass",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        updated = db.session.get(User, target_user_id)
        assert updated.password_hash != before_hash
        assert updated.check_password("after-pass")

    logs = list_audit_logs(action="admin_user_update")
    assert len(logs) == 1
    metadata = json.loads(logs[0].metadata_json)
    assert metadata["password_changed"] is True


def test_ユーザー更新で他ユーザーと重複するメールアドレスは拒否される(
    client,
    login_as_admin,
    set_csrf_token,
    create_user,
    app,
    list_audit_logs,
):
    """ユーザー更新で他ユーザーと重複するメールアドレスは拒否される。"""
    login_as_admin(username="admin-update-dup-email", password="admin-pass")
    owner_id = create_user(username="mail-owner", password="pass", email="owner@example.com")
    target_id = create_user(username="mail-target", password="pass", email="target@example.com")
    token = set_csrf_token(client)

    response = client.post(
        "/admin/users",
        data={
            "csrf_token": token,
            "action": "update",
            "user_id": str(target_id),
            "name": "変更試行",
            "email": "owner@example.com",
            "role": "user",
            "password": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        owner = db.session.get(User, owner_id)
        target = db.session.get(User, target_id)
        assert owner.email == "owner@example.com"
        assert target.email == "target@example.com"
    assert list_audit_logs(action="admin_user_update") == []


def test_ユーザー更新で存在しないユーザーidは404になる(client, login_as_admin, set_csrf_token):
    """ユーザー更新で存在しないユーザーIDは404になる。"""
    login_as_admin(username="admin-update-404", password="admin-pass")
    token = set_csrf_token(client)

    response = client.post(
        "/admin/users",
        data={
            "csrf_token": token,
            "action": "update",
            "user_id": "999999",
            "name": "存在しない",
            "email": "none@example.com",
            "role": "user",
            "password": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 404


def test_ユーザー更新でdbコミット失敗時はロールバックされる(
    client,
    login_as_admin,
    set_csrf_token,
    create_user,
    monkeypatch,
    app,
    list_audit_logs,
):
    """ユーザー更新でDBコミット失敗時はロールバックされる。"""
    login_as_admin(username="admin-update-rollback", password="admin-pass")
    target_user_id = create_user(
        username="rollback-target",
        password="before-pass",
        name="before-name",
        email="before-rollback@example.com",
        role="user",
    )
    token = set_csrf_token(client)

    def _raise_integrity_error():
        raise IntegrityError("forced", {}, Exception("forced"))

    monkeypatch.setattr(db.session, "commit", _raise_integrity_error)

    response = client.post(
        "/admin/users",
        data={
            "csrf_token": token,
            "action": "update",
            "user_id": str(target_user_id),
            "name": "after-name",
            "email": "after-rollback@example.com",
            "role": "admin",
            "password": "after-pass",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        target = db.session.get(User, target_user_id)
        assert target.name == "before-name"
        assert target.email == "before-rollback@example.com"
        assert target.role == "user"
        assert target.check_password("before-pass")
    assert list_audit_logs(action="admin_user_update") == []


def test_ユーザー削除成功時は対象ユーザーを削除し既存監査ログのuser_idをnull化する(
    client,
    login_as_admin,
    set_csrf_token,
    create_user,
    create_audit_log,
    app,
    list_audit_logs,
):
    """ユーザー削除成功時は対象ユーザーを削除し既存監査ログのuser_idをNULL化する。"""
    login_as_admin(username="admin-delete", password="admin-pass")
    target_user_id = create_user(
        username="delete-target",
        password="delete-pass",
        email="delete@example.com",
        role="user",
    )
    create_audit_log(
        action="clock_in",
        user_id=target_user_id,
        target_type="shift",
        target_id=1,
        metadata_dict={"marker": "before-delete"},
    )
    token = set_csrf_token(client)

    response = client.post(
        "/admin/users",
        data={
            "csrf_token": token,
            "action": "delete",
            "user_id": str(target_user_id),
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(User, target_user_id) is None
        clock_in_log = AuditLog.query.filter_by(action="clock_in").first()
        assert clock_in_log is not None
        assert clock_in_log.user_id is None

    logs = list_audit_logs(action="admin_user_delete")
    assert len(logs) == 1
    metadata = json.loads(logs[0].metadata_json)
    assert metadata["username"] == "delete-target"


def test_自分自身のユーザー削除は拒否される(
    client,
    login_as_admin,
    set_csrf_token,
    app,
    list_audit_logs,
):
    """自分自身のユーザー削除は拒否される。"""
    admin_id = login_as_admin(username="admin-self-delete", password="admin-pass")
    token = set_csrf_token(client)

    response = client.post(
        "/admin/users",
        data={
            "csrf_token": token,
            "action": "delete",
            "user_id": str(admin_id),
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(User, admin_id) is not None
    assert list_audit_logs(action="admin_user_delete") == []


def test_ユーザー削除で存在しないユーザーidは404になる(client, login_as_admin, set_csrf_token):
    """ユーザー削除で存在しないユーザーIDは404になる。"""
    login_as_admin(username="admin-delete-404", password="admin-pass")
    token = set_csrf_token(client)

    response = client.post(
        "/admin/users",
        data={
            "csrf_token": token,
            "action": "delete",
            "user_id": "999999",
        },
        follow_redirects=False,
    )

    assert response.status_code == 404


def test_未知のactionを送信した場合は副作用なく一覧を再表示する(
    client,
    login_as_admin,
    set_csrf_token,
    app,
    list_audit_logs,
):
    """未知のactionを送信した場合は副作用なく一覧を再表示する。"""
    login_as_admin(username="admin-unknown-action", password="admin-pass")
    token = set_csrf_token(client)
    with app.app_context():
        before_user_count = User.query.count()

    response = client.post(
        "/admin/users",
        data={
            "csrf_token": token,
            "action": "unknown-action",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert "ユーザー管理".encode("utf-8") in response.data
    with app.app_context():
        assert User.query.count() == before_user_count
    assert list_audit_logs(action="admin_user_create") == []
    assert list_audit_logs(action="admin_user_update") == []
    assert list_audit_logs(action="admin_user_delete") == []
