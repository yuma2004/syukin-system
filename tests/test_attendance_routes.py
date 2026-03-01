from datetime import datetime, timezone

from app import Break, Shift, db


def test_出勤成功で開いているシフトと監査ログが作成される(
    client,
    login_as,
    set_csrf_token,
    list_audit_logs,
    app,
):
    """出勤成功で開いているシフトと監査ログが作成される。"""
    login_as(username="worker1", password="secret-pass")
    token = set_csrf_token(client)

    response = client.post(
        "/clock/in",
        data={"csrf_token": token},
        headers={"User-Agent": "pytest-agent"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

    with app.app_context():
        shifts = Shift.query.all()
        assert len(shifts) == 1
        assert shifts[0].clock_out_at is None

    logs = list_audit_logs(action="clock_in")
    assert len(logs) == 1


def test_出勤中に再度出勤すると400になる(client, login_as, set_csrf_token, app):
    """出勤中に再度出勤すると400になる。"""
    login_as(username="worker2", password="secret-pass")
    token = set_csrf_token(client)
    first = client.post("/clock/in", data={"csrf_token": token}, follow_redirects=False)
    assert first.status_code == 302

    second = client.post("/clock/in", data={"csrf_token": token}, follow_redirects=False)

    assert second.status_code == 400
    with app.app_context():
        assert Shift.query.count() == 1


def test_出勤中のシフトがない状態で退勤すると400になる(client, login_as, set_csrf_token):
    """出勤中のシフトがない状態で退勤すると400になる。"""
    login_as(username="worker3", password="secret-pass")
    token = set_csrf_token(client)

    response = client.post("/clock/out", data={"csrf_token": token}, follow_redirects=False)

    assert response.status_code == 400


def test_休憩中に退勤すると休憩が自動終了して退勤が記録される(
    client,
    login_as,
    create_shift,
    set_csrf_token,
    list_audit_logs,
    app,
):
    """休憩中に退勤すると休憩が自動終了して退勤が記録される。"""
    user_id = login_as(username="worker4", password="secret-pass")
    create_shift(
        user_id=user_id,
        clock_in_at=datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc),
        break_start_at=datetime(2026, 1, 5, 1, 0, tzinfo=timezone.utc),
    )
    token = set_csrf_token(client)

    response = client.post("/clock/out", data={"csrf_token": token}, follow_redirects=False)

    assert response.status_code == 302
    with app.app_context():
        shift = Shift.query.first()
        assert shift.clock_out_at is not None
        open_break = Break.query.filter_by(shift_id=shift.id, end_at=None).first()
        assert open_break is None

    logs = list_audit_logs(action="clock_out")
    assert len(logs) == 1


def test_出勤していない状態で休憩開始すると400になる(client, login_as, set_csrf_token):
    """出勤していない状態で休憩開始すると400になる。"""
    login_as(username="worker5", password="secret-pass")
    token = set_csrf_token(client)

    response = client.post("/break/start", data={"csrf_token": token}, follow_redirects=False)

    assert response.status_code == 400


def test_休憩中に再度休憩開始すると400になる(client, login_as, create_shift, set_csrf_token):
    """休憩中に再度休憩開始すると400になる。"""
    user_id = login_as(username="worker6", password="secret-pass")
    create_shift(
        user_id=user_id,
        clock_in_at=datetime(2026, 1, 6, 0, 0, tzinfo=timezone.utc),
        break_start_at=datetime(2026, 1, 6, 1, 0, tzinfo=timezone.utc),
    )
    token = set_csrf_token(client)

    response = client.post("/break/start", data={"csrf_token": token}, follow_redirects=False)

    assert response.status_code == 400


def test_休憩がない状態で休憩終了すると400になる(client, login_as, create_shift, set_csrf_token):
    """休憩がない状態で休憩終了すると400になる。"""
    user_id = login_as(username="worker7", password="secret-pass")
    create_shift(user_id=user_id, clock_in_at=datetime(2026, 1, 7, 0, 0, tzinfo=timezone.utc))
    token = set_csrf_token(client)

    response = client.post("/break/end", data={"csrf_token": token}, follow_redirects=False)

    assert response.status_code == 400


def test_休憩終了成功で監査ログが記録される(
    client,
    login_as,
    create_shift,
    set_csrf_token,
    list_audit_logs,
    app,
):
    """休憩終了成功で監査ログが記録される。"""
    user_id = login_as(username="worker8", password="secret-pass")
    create_shift(
        user_id=user_id,
        clock_in_at=datetime(2026, 1, 8, 0, 0, tzinfo=timezone.utc),
        break_start_at=datetime(2026, 1, 8, 1, 0, tzinfo=timezone.utc),
    )
    token = set_csrf_token(client)

    response = client.post("/break/end", data={"csrf_token": token}, follow_redirects=False)

    assert response.status_code == 302
    with app.app_context():
        assert Break.query.filter(Break.end_at.isnot(None)).count() == 1

    logs = list_audit_logs(action="break_end")
    assert len(logs) == 1
