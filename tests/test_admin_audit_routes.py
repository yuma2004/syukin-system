import csv
import json
import re
from io import StringIO


def _csv_rows_from_response(response):
    csv_text = response.data.decode("utf-8-sig")
    return list(csv.DictReader(StringIO(csv_text)))


def test_未ログインで監査ログ画面にアクセスするとログイン画面へリダイレクトされる(client):
    """未ログインで監査ログ画面にアクセスするとログイン画面へリダイレクトされる。"""
    response = client.get("/admin/audit", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_一般ユーザーは監査ログ画面へアクセスできず403になる(client, login_as):
    """一般ユーザーは監査ログ画面へアクセスできず403になる。"""
    login_as(username="member-audit", password="member-pass", role="user")

    response = client.get("/admin/audit", follow_redirects=False)

    assert response.status_code == 403


def test_監査ログ画面でactionフィルタが効く(
    client,
    login_as_admin,
    create_audit_log,
):
    """監査ログ画面でactionフィルタが効く。"""
    login_as_admin(username="admin-audit-action", password="admin-pass")
    create_audit_log(action="clock_in", metadata_dict={"marker": "clock-in-only"})
    create_audit_log(action="clock_out", metadata_dict={"marker": "clock-out-only"})

    response = client.get("/admin/audit?action=clock_in", follow_redirects=False)

    assert response.status_code == 200
    text = response.data.decode("utf-8")
    assert "clock-in-only" in text
    assert "clock-out-only" not in text


def test_監査ログ画面でusernameフィルタが効く(
    client,
    login_as_admin,
    create_user,
    create_audit_log,
):
    """監査ログ画面でusernameフィルタが効く。"""
    login_as_admin(username="admin-audit-username", password="admin-pass")
    user_a = create_user(username="audit-user-a", password="user-pass")
    user_b = create_user(username="audit-user-b", password="user-pass")
    create_audit_log(action="clock_in", user_id=user_a, metadata_dict={"marker": "user-a-only"})
    create_audit_log(action="clock_in", user_id=user_b, metadata_dict={"marker": "user-b-only"})

    response = client.get("/admin/audit?username=audit-user-a", follow_redirects=False)

    assert response.status_code == 200
    text = response.data.decode("utf-8")
    assert "user-a-only" in text
    assert "user-b-only" not in text


def test_監査ログ画面のlimitが数値以外ならデフォルト200が使われる(
    client,
    login_as_admin,
):
    """監査ログ画面のlimitが数値以外ならデフォルト200が使われる。"""
    login_as_admin(username="admin-audit-limit-default", password="admin-pass")

    response = client.get("/admin/audit?limit=not-number", follow_redirects=False)

    assert response.status_code == 200
    text = response.data.decode("utf-8")
    assert re.search(r'name="limit"[^>]*value="200"', text) is not None


def test_監査ログ画面のlimitが0以下なら1にクランプされる(
    client,
    login_as_admin,
):
    """監査ログ画面のlimitが0以下なら1にクランプされる。"""
    login_as_admin(username="admin-audit-limit-min", password="admin-pass")

    response = client.get("/admin/audit?limit=0", follow_redirects=False)

    assert response.status_code == 200
    text = response.data.decode("utf-8")
    assert re.search(r'name="limit"[^>]*value="1"', text) is not None


def test_監査ログ画面のlimitが500を超えると500にクランプされる(
    client,
    login_as_admin,
):
    """監査ログ画面のlimitが500を超えると500にクランプされる。"""
    login_as_admin(username="admin-audit-limit-max", password="admin-pass")

    response = client.get("/admin/audit?limit=9999", follow_redirects=False)

    assert response.status_code == 200
    text = response.data.decode("utf-8")
    assert re.search(r'name="limit"[^>]*value="500"', text) is not None


def test_監査ログ画面は不正jsonメタデータでも表示できる(
    client,
    login_as_admin,
    create_audit_log,
):
    """監査ログ画面は不正JSONメタデータでも表示できる。"""
    login_as_admin(username="admin-audit-bad-json", password="admin-pass")
    create_audit_log(
        action="clock_in",
        metadata_json='{"broken"',
    )

    response = client.get("/admin/audit", follow_redirects=False)

    assert response.status_code == 200
    text = response.data.decode("utf-8")
    assert "raw" in text
    assert "broken" in text


def test_未ログインで監査ログcsvエクスポートにアクセスするとログイン画面へリダイレクトされる(client):
    """未ログインで監査ログCSVエクスポートにアクセスするとログイン画面へリダイレクトされる。"""
    response = client.get("/admin/audit/export", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_一般ユーザーは監査ログcsvエクスポートを実行できず403になる(client, login_as):
    """一般ユーザーは監査ログCSVエクスポートを実行できず403になる。"""
    login_as(username="member-audit-export", password="member-pass", role="user")

    response = client.get("/admin/audit/export", follow_redirects=False)

    assert response.status_code == 403


def test_監査ログcsvエクスポートはbom付きでactionフィルタを反映する(
    client,
    login_as_admin,
    create_audit_log,
    list_audit_logs,
):
    """監査ログCSVエクスポートはBOM付きでactionフィルタを反映する。"""
    login_as_admin(username="admin-export-action", password="admin-pass")
    create_audit_log(action="clock_in", metadata_dict={"marker": "export-action-hit"})
    create_audit_log(action="clock_out", metadata_dict={"marker": "export-action-skip"})

    response = client.get("/admin/audit/export?action=clock_in", follow_redirects=False)

    assert response.status_code == 200
    assert response.data.startswith(b"\xef\xbb\xbf")
    rows = _csv_rows_from_response(response)
    assert rows
    assert all(row["action"] == "clock_in" for row in rows)
    assert any("export-action-hit" in row["metadata_json"] for row in rows)
    assert all("export-action-skip" not in row["metadata_json"] for row in rows)

    logs = list_audit_logs(action="admin_audit_export")
    assert len(logs) == 1


def test_監査ログcsvエクスポートはusernameフィルタを反映する(
    client,
    login_as_admin,
    create_user,
    create_audit_log,
    list_audit_logs,
):
    """監査ログCSVエクスポートはusernameフィルタを反映する。"""
    login_as_admin(username="admin-export-username", password="admin-pass")
    user_a = create_user(username="export-user-a", password="user-pass", email="a@example.com")
    user_b = create_user(username="export-user-b", password="user-pass", email="b@example.com")
    create_audit_log(action="clock_in", user_id=user_a, metadata_dict={"marker": "export-user-a"})
    create_audit_log(action="clock_in", user_id=user_b, metadata_dict={"marker": "export-user-b"})

    response = client.get("/admin/audit/export?username=export-user-a", follow_redirects=False)

    assert response.status_code == 200
    rows = _csv_rows_from_response(response)
    assert rows
    assert all(row["user_username"] == "export-user-a" for row in rows)
    assert any("export-user-a" in row["metadata_json"] for row in rows)
    assert all("export-user-b" not in row["metadata_json"] for row in rows)

    logs = list_audit_logs(action="admin_audit_export")
    assert len(logs) == 1
    metadata = json.loads(logs[0].metadata_json)
    assert metadata["username"] == "export-user-a"


def test_監査ログcsvエクスポートのlimitが数値以外なら1000が使われる(
    client,
    login_as_admin,
    create_audit_log,
    list_audit_logs,
):
    """監査ログCSVエクスポートのlimitが数値以外なら1000が使われる。"""
    login_as_admin(username="admin-export-limit-default", password="admin-pass")
    create_audit_log(action="clock_in", metadata_dict={"marker": "limit-default"})

    response = client.get("/admin/audit/export?limit=abc", follow_redirects=False)

    assert response.status_code == 200
    logs = list_audit_logs(action="admin_audit_export")
    assert len(logs) == 1
    metadata = json.loads(logs[0].metadata_json)
    assert metadata["limit"] == 1000


def test_監査ログcsvエクスポートのlimitが0以下なら1にクランプされる(
    client,
    login_as_admin,
    create_audit_log,
    list_audit_logs,
):
    """監査ログCSVエクスポートのlimitが0以下なら1にクランプされる。"""
    login_as_admin(username="admin-export-limit-min", password="admin-pass")
    create_audit_log(action="clock_in", metadata_dict={"marker": "limit-min-a"})
    create_audit_log(action="clock_out", metadata_dict={"marker": "limit-min-b"})

    response = client.get("/admin/audit/export?limit=0", follow_redirects=False)

    assert response.status_code == 200
    rows = _csv_rows_from_response(response)
    assert len(rows) == 1
    logs = list_audit_logs(action="admin_audit_export")
    metadata = json.loads(logs[0].metadata_json)
    assert metadata["limit"] == 1
    assert metadata["count"] == 1


def test_監査ログcsvエクスポートのlimitが5000を超えると5000にクランプされる(
    client,
    login_as_admin,
    create_audit_log,
    list_audit_logs,
):
    """監査ログCSVエクスポートのlimitが5000を超えると5000にクランプされる。"""
    login_as_admin(username="admin-export-limit-max", password="admin-pass")
    create_audit_log(action="clock_in", metadata_dict={"marker": "limit-max"})

    response = client.get("/admin/audit/export?limit=99999", follow_redirects=False)

    assert response.status_code == 200
    logs = list_audit_logs(action="admin_audit_export")
    assert len(logs) == 1
    metadata = json.loads(logs[0].metadata_json)
    assert metadata["limit"] == 5000


def test_監査ログcsvエクスポートは不正jsonメタデータをrawとして出力できる(
    client,
    login_as_admin,
    create_audit_log,
):
    """監査ログCSVエクスポートは不正JSONメタデータをrawとして出力できる。"""
    login_as_admin(username="admin-export-bad-json", password="admin-pass")
    create_audit_log(action="clock_in", metadata_json='{"broken"', target_type="shift", target_id=10)

    response = client.get("/admin/audit/export?action=clock_in", follow_redirects=False)

    assert response.status_code == 200
    rows = _csv_rows_from_response(response)
    assert rows
    assert any("raw" in row["metadata_json"] and "broken" in row["metadata_json"] for row in rows)


def test_監査ログcsvはエクスポート操作自体のログを含めないが実行後に記録は残る(
    client,
    login_as_admin,
    create_audit_log,
    list_audit_logs,
):
    """監査ログCSVはエクスポート操作自体のログを含めないが実行後に記録は残る。"""
    login_as_admin(username="admin-export-self-log", password="admin-pass")
    create_audit_log(action="clock_in", metadata_dict={"marker": "self-log-check"})

    response = client.get("/admin/audit/export", follow_redirects=False)

    assert response.status_code == 200
    rows = _csv_rows_from_response(response)
    actions = [row["action"] for row in rows]
    assert "admin_audit_export" not in actions

    export_logs = list_audit_logs(action="admin_audit_export")
    assert len(export_logs) == 1
