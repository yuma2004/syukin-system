def test_未ログインで管理画面にアクセスするとログイン画面へリダイレクトされる(client):
    """未ログインで管理画面にアクセスするとログイン画面へリダイレクトされる。"""
    response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_一般ユーザーは管理画面へアクセスできず403になる(client, login_as):
    """一般ユーザーは管理画面へアクセスできず403になる。"""
    login_as(username="normal-user", password="secret-pass", role="user")

    response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 403


def test_一般ユーザーは管理者用のシフト編集apiへアクセスできず403になる(client, login_as, create_user, create_shift):
    """一般ユーザーは管理者用のシフト編集APIへアクセスできず403になる。"""
    admin_user_id = create_user(
        username="admin-owner",
        password="admin-pass",
        role="admin",
    )
    shift_id = create_shift(user_id=admin_user_id)
    login_as(username="normal-user2", password="secret-pass", role="user")

    response = client.get(f"/admin/shift/{shift_id}", follow_redirects=False)

    assert response.status_code == 403


def test_csrfトークンがない投稿は400になる(client, login_as):
    """CSRFトークンがない投稿は400になる。"""
    login_as(username="csrf-user", password="secret-pass", role="user")

    response = client.post("/clock/in", data={}, follow_redirects=False)

    assert response.status_code == 400
