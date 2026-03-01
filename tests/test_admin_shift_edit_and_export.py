import csv
import json
from datetime import datetime, timezone
from io import StringIO
from zoneinfo import ZoneInfo

from app import Break, Shift, db


def _as_utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def test_管理者はシフトを作成でき監査ログが残る(
    client,
    login_as,
    create_user,
    set_csrf_token,
    list_audit_logs,
    app,
):
    """管理者はシフトを作成でき監査ログが残る。"""
    login_as(username="admin1", password="admin-pass", role="admin")
    target_user_id = create_user(username="member1", password="member-pass")
    token = set_csrf_token(client)

    response = client.post(
        "/admin/shift/create",
        data={
            "csrf_token": token,
            "user_id": str(target_user_id),
            "clock_in_at": "2026-01-10T09:00",
            "clock_out_at": "2026-01-10T18:00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/admin" in response.headers["Location"]

    with app.app_context():
        shifts = Shift.query.filter_by(user_id=target_user_id).all()
        assert len(shifts) == 1
        assert shifts[0].clock_out_at is not None

    logs = list_audit_logs(action="admin_shift_create")
    assert len(logs) == 1
    metadata = json.loads(logs[0].metadata_json)
    assert metadata["user_username"] == "member1"


def test_管理者シフト作成で退勤が出勤より早いと追加されない(
    client,
    login_as,
    create_user,
    set_csrf_token,
    app,
):
    """管理者シフト作成で退勤が出勤より早いと追加されない。"""
    login_as(username="admin2", password="admin-pass", role="admin")
    target_user_id = create_user(username="member2", password="member-pass")
    token = set_csrf_token(client)

    response = client.post(
        "/admin/shift/create",
        data={
            "csrf_token": token,
            "user_id": str(target_user_id),
            "clock_in_at": "2026-01-11T10:00",
            "clock_out_at": "2026-01-11T09:59",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        assert Shift.query.filter_by(user_id=target_user_id).count() == 0


def test_管理者のシフト更新で変更前後を含む監査ログが記録される(
    client,
    login_as,
    create_user,
    create_shift,
    set_csrf_token,
    list_audit_logs,
    app,
):
    """管理者のシフト更新で変更前後を含む監査ログが記録される。"""
    login_as(username="admin3", password="admin-pass", role="admin")
    target_user_id = create_user(
        username="member3",
        password="member-pass",
        email="member3@example.com",
    )
    shift_id = create_shift(
        user_id=target_user_id,
        clock_in_at=datetime(2026, 1, 12, 0, 0, tzinfo=timezone.utc),
        clock_out_at=datetime(2026, 1, 12, 9, 0, tzinfo=timezone.utc),
    )
    token = set_csrf_token(client)

    response = client.post(
        f"/admin/shift/{shift_id}/edit",
        data={
            "csrf_token": token,
            "action": "update_shift",
            "clock_in_at": "2026-01-12T09:30",
            "clock_out_at": "2026-01-12T18:30",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/admin" in response.headers["Location"]

    expected_clock_in_utc = datetime(2026, 1, 12, 9, 30, tzinfo=ZoneInfo("Asia/Tokyo")).astimezone(timezone.utc)
    expected_clock_out_utc = datetime(2026, 1, 12, 18, 30, tzinfo=ZoneInfo("Asia/Tokyo")).astimezone(timezone.utc)
    with app.app_context():
        shift = db.session.get(Shift, shift_id)
        assert _as_utc(shift.clock_in_at) == expected_clock_in_utc
        assert _as_utc(shift.clock_out_at) == expected_clock_out_utc

    logs = list_audit_logs(action="admin_shift_edit")
    assert len(logs) == 1
    metadata = json.loads(logs[0].metadata_json)
    assert "old_values" in metadata
    assert "new_values" in metadata
    assert metadata["new_values"]["clock_in_at"] is not None
    assert metadata["new_values"]["clock_out_at"] is not None


def test_管理者は休憩の追加更新削除リセットを実行できる(
    client,
    login_as,
    create_user,
    create_shift,
    set_csrf_token,
    list_audit_logs,
    app,
):
    """管理者は休憩の追加更新削除リセットを実行できる。"""
    login_as(username="admin4", password="admin-pass", role="admin")
    target_user_id = create_user(username="member4", password="member-pass")
    shift_id = create_shift(
        user_id=target_user_id,
        clock_in_at=datetime(2026, 1, 13, 0, 0, tzinfo=timezone.utc),
    )
    token = set_csrf_token(client)

    add_resp = client.post(
        f"/admin/shift/{shift_id}/edit",
        data={
            "csrf_token": token,
            "action": "break_add",
            "start_at": "2026-01-13T10:00",
            "end_at": "2026-01-13T10:30",
        },
        follow_redirects=False,
    )
    assert add_resp.status_code == 302

    with app.app_context():
        breaks = Break.query.filter_by(shift_id=shift_id).order_by(Break.id.asc()).all()
        assert len(breaks) == 1
        break_id = breaks[0].id

    update_resp = client.post(
        f"/admin/shift/{shift_id}/edit",
        data={
            "csrf_token": token,
            "action": "break_update",
            "break_id": str(break_id),
            "start_at": "2026-01-13T10:15",
            "end_at": "2026-01-13T10:45",
        },
        follow_redirects=False,
    )
    assert update_resp.status_code == 302

    with app.app_context():
        updated = db.session.get(Break, break_id)
        assert updated is not None
        assert _as_utc(updated.start_at).hour == 1
        assert _as_utc(updated.start_at).minute == 15

    delete_resp = client.post(
        f"/admin/shift/{shift_id}/edit",
        data={
            "csrf_token": token,
            "action": "break_delete",
            "break_id": str(break_id),
        },
        follow_redirects=False,
    )
    assert delete_resp.status_code == 302
    with app.app_context():
        assert Break.query.filter_by(shift_id=shift_id).count() == 0

    client.post(
        f"/admin/shift/{shift_id}/edit",
        data={
            "csrf_token": token,
            "action": "break_add",
            "start_at": "2026-01-13T11:00",
            "end_at": "2026-01-13T11:30",
        },
        follow_redirects=False,
    )
    client.post(
        f"/admin/shift/{shift_id}/edit",
        data={
            "csrf_token": token,
            "action": "break_add",
            "start_at": "2026-01-13T12:00",
            "end_at": "2026-01-13T12:30",
        },
        follow_redirects=False,
    )
    with app.app_context():
        assert Break.query.filter_by(shift_id=shift_id).count() == 2

    reset_resp = client.post(
        f"/admin/shift/{shift_id}/edit",
        data={
            "csrf_token": token,
            "action": "break_reset",
        },
        follow_redirects=False,
    )
    assert reset_resp.status_code == 302
    with app.app_context():
        assert Break.query.filter_by(shift_id=shift_id).count() == 0

    assert len(list_audit_logs(action="admin_break_add")) >= 3
    assert len(list_audit_logs(action="admin_break_update")) == 1
    assert len(list_audit_logs(action="admin_break_delete")) == 1
    assert len(list_audit_logs(action="admin_break_reset")) == 1


def test_管理者のシフト詳細apiは編集画面向けjsonを返す(
    client,
    login_as,
    create_user,
    create_shift,
):
    """管理者のシフト詳細APIは編集画面向けJSONを返す。"""
    login_as(username="admin5", password="admin-pass", role="admin")
    target_user_id = create_user(username="member5", password="member-pass", email="member5@example.com")
    shift_id = create_shift(
        user_id=target_user_id,
        clock_in_at=datetime(2026, 1, 14, 0, 0, tzinfo=timezone.utc),
        clock_out_at=datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc),
        break_start_at=datetime(2026, 1, 14, 3, 0, tzinfo=timezone.utc),
        break_end_at=datetime(2026, 1, 14, 4, 0, tzinfo=timezone.utc),
    )

    response = client.get(f"/admin/shift/{shift_id}", follow_redirects=False)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["id"] == shift_id
    assert payload["user_username"] == "member5"
    assert payload["break_count"] == 1
    assert payload["worked_seconds"] > 0
    assert payload["clock_in_form"]


def test_管理者csvエクスポートはbom付きcsvを返す(
    client,
    login_as,
    create_user,
    create_shift,
    list_audit_logs,
):
    """管理者CSVエクスポートはBOM付きCSVを返す。"""
    login_as(username="admin6", password="admin-pass", role="admin")
    target_user_id = create_user(username="member6", password="member-pass", email="member6@example.com")
    create_shift(
        user_id=target_user_id,
        clock_in_at=datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc),
        clock_out_at=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
    )

    response = client.get(
        "/admin/export?start=2026-01-15&end=2026-01-15",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert response.data.startswith(b"\xef\xbb\xbf")
    csv_text = response.data.decode("utf-8-sig")
    assert csv_text.splitlines()[0].startswith("user_username,user_email,user_name")
    assert "member6" in csv_text

    logs = list_audit_logs(action="admin_export")
    assert len(logs) == 1


def test_管理者csvエクスポートは日付形式が不正だと400になる(client, login_as):
    """管理者CSVエクスポートは日付形式が不正だと400になる。"""
    login_as(username="admin7", password="admin-pass", role="admin")

    response = client.get("/admin/export?start=not-a-date&end=2026-01-16", follow_redirects=False)

    assert response.status_code == 400


def test_管理者csvエクスポートは最大期間を超えると400になる(client, login_as):
    """管理者CSVエクスポートは最大期間を超えると400になる。"""
    login_as(username="admin8", password="admin-pass", role="admin")

    response = client.get("/admin/export?start=2024-01-01&end=2026-01-31", follow_redirects=False)

    assert response.status_code == 400


def test_管理者csvエクスポートはusernameフィルタで対象ユーザーのみ出力する(
    client,
    login_as,
    create_user,
    create_shift,
):
    """管理者CSVエクスポートはusernameフィルタで対象ユーザーのみ出力する。"""
    login_as(username="admin9", password="admin-pass", role="admin")
    target1 = create_user(username="target-a", password="member-pass")
    target2 = create_user(username="target-b", password="member-pass")
    create_shift(
        user_id=target1,
        clock_in_at=datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc),
        clock_out_at=datetime(2026, 1, 16, 9, 0, tzinfo=timezone.utc),
    )
    create_shift(
        user_id=target2,
        clock_in_at=datetime(2026, 1, 16, 1, 0, tzinfo=timezone.utc),
        clock_out_at=datetime(2026, 1, 16, 10, 0, tzinfo=timezone.utc),
    )

    response = client.get(
        "/admin/export?start=2026-01-16&end=2026-01-16&username=target-a",
        follow_redirects=False,
    )

    assert response.status_code == 200
    rows = list(csv.DictReader(StringIO(response.data.decode("utf-8-sig"))))
    assert rows
    assert all(row["user_username"] == "target-a" for row in rows)
