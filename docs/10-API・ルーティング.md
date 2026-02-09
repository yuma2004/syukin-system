# API・ルーティング

## 概要

本システムは Blueprint 構成でルーティングを管理しています。

- `attendance_app/routes/auth.py`
- `attendance_app/routes/attendance.py`
- `attendance_app/routes/admin.py`
- `attendance_app/routes/audit.py`
- `attendance_app/routes/health.py`

## エンドポイント一覧

### 認証

- `GET/POST /login`
  - 認証不要
  - ログインフォーム表示・認証
- `POST /logout`
  - ログイン必須
  - ログアウト

### ダッシュボード・打刻

- `GET /`
- `GET /dashboard`
  - ログイン必須
  - ダッシュボード表示
- `POST /clock/in`
  - 出勤記録
- `POST /clock/out`
  - 退勤記録
- `POST /break/start`
  - 休憩開始
- `POST /break/end`
  - 休憩終了

### 管理画面（管理者のみ）

- `GET /admin`
  - 出退勤記録一覧（期間/ユーザーIDフィルタ）
- `POST /admin/shift/create`
  - 手動シフト作成
- `POST /admin/shift/<shift_id>/delete`
  - シフト削除
- `GET /admin/shift/<shift_id>/edit`
  - シフト編集画面
- `POST /admin/shift/<shift_id>/edit`
  - シフト更新、休憩追加/更新/削除/リセット
- `GET /admin/shift/<shift_id>`
  - シフト詳細JSON（モーダル用）
- `GET /admin/export`
  - 出退勤CSVエクスポート
- `GET/POST /admin/users`
  - ユーザー一覧/作成/更新/削除

### 監査ログ（管理者のみ）

- `GET /admin/audit`
  - 監査ログ閲覧（action/username/limit フィルタ）
- `GET /admin/audit/export`
  - 監査ログCSVエクスポート

### ヘルスチェック

- `GET /healthz`
  - `ok` を返す

## 共通ルール

- 管理系エンドポイントは `require_admin()` で権限検証
- フォームPOSTは `verify_csrf()` を通過必須（テスト時は設定で無効化可能）
- 期間指定は最大 `CSV_EXPORT_MAX_DAYS` 日まで

## 主なレスポンス/エラー

- `400`: CSRF不正、入力不正、日付範囲不正、業務前提違反
- `403`: 管理者権限不足
- `404`: 対象データ未存在

## 関連

- `docs/03-ダッシュボード・出退勤機能.md`
- `docs/04-管理者機能（出退勤記録管理）.md`
- `docs/06-監査ログ機能.md`
