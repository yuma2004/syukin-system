import json

from app import User, db


def test_正常なログインで最終ログイン時刻と監査ログが更新される(
    client,
    create_user,
    set_csrf_token,
    list_audit_logs,
    app,
):
    """正常なログインで最終ログイン時刻と監査ログが更新される。"""
    create_user(username="alice", password="correct-password")
    token = set_csrf_token(client)

    response = client.post(
        "/login",
        data={
            "username": "alice",
            "password": "correct-password",
            "csrf_token": token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

    with app.app_context():
        user = User.query.filter_by(username="alice").first()
        assert user is not None
        assert user.last_login_at is not None

    logs = list_audit_logs(action="login")
    assert len(logs) == 1
    assert json.loads(logs[0].metadata_json)["username"] == "alice"


def test_パスワード不一致のログインでは失敗して監査ログが増えない(
    client,
    create_user,
    set_csrf_token,
    list_audit_logs,
):
    """パスワード不一致のログインでは失敗して監査ログが増えない。"""
    create_user(username="bob", password="correct-password")
    token = set_csrf_token(client)

    response = client.post(
        "/login",
        data={
            "username": "bob",
            "password": "wrong-password",
            "csrf_token": token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert list_audit_logs(action="login") == []


def test_ログアウトはcsrf不正だと400になる(client, login_as):
    """ログアウトはcsrf不正だと400になる。"""
    login_as(username="carol", password="secret-pass")

    response = client.post("/logout", data={}, follow_redirects=False)

    assert response.status_code == 400


def test_ログアウト成功時は監査ログを記録してログイン画面へ戻る(
    client,
    login_as,
    set_csrf_token,
    list_audit_logs,
):
    """ログアウト成功時は監査ログを記録してログイン画面へ戻る。"""
    login_as(username="dave", password="secret-pass")
    token = set_csrf_token(client)

    response = client.post(
        "/logout",
        data={"csrf_token": token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

    logs = list_audit_logs(action="logout")
    assert len(logs) == 1

    after_logout = client.get("/", follow_redirects=False)
    assert after_logout.status_code == 302
    assert "/login" in after_logout.headers["Location"]
