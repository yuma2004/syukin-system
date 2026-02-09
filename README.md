# 出退勤システム（Flask / App Factory）

Dockerを使わずにローカル実行でき、PaaS（Render等）にそのままデプロイできる出退勤管理システムです。

## 技術スタック

- Python 3.11+
- Flask 3.x
- Flask-Login
- Flask-SQLAlchemy / SQLAlchemy 2.x
- DB: SQLite（ローカル） / PostgreSQL（本番推奨）

## クイックスタート

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate

pip install -r requirements-test.txt
alembic upgrade head
flask --app app run -p 8000
```

- `http://localhost:8000` にアクセス
- 初回は管理者ユーザーを作成してください（後述）

## 初期管理者ユーザー作成

```bash
python
```

```python
from app import app, db, User

with app.app_context():
    admin = User(username="admin", role="admin", name="管理者")
    admin.set_password("change-me")
    db.session.add(admin)
    db.session.commit()
```

## 品質チェック

```bash
# テスト
python -m pytest

# 静的解析
python -m ruff check .
```

## デプロイ

- `Procfile` は `web: gunicorn app:app` を使用
- 環境変数:
  - `SECRET_KEY`
  - `DATABASE_URL`
  - `TIMEZONE`（デフォルト: `Asia/Tokyo`）
  - `SESSION_COOKIE_SECURE`（本番は `true` 推奨）
  - `REMEMBER_COOKIE_DAYS`（ログイン保持の有効日数、デフォルト: `14`）

## マイグレーション基盤（Alembic）

今回のリファクタで Alembic の骨組みを追加しています。

```bash
# 例: 初回差分生成（将来運用時）
alembic revision --autogenerate -m "init"
alembic upgrade head
```

現時点では既存 `init-db` 運用と互換です。

## プロジェクト構成

```text
syukin-system/
├── app.py                      # 互換エントリ（app=create_app()）
├── attendance_app/
│   ├── __init__.py             # create_app()
│   ├── config.py
│   ├── extensions.py
│   ├── cli.py
│   ├── authz.py
│   ├── models/
│   ├── routes/
│   ├── services/
│   └── utils/
├── templates/
│   ├── partials/
│   └── *.html
├── static/
│   ├── style.css
│   └── js/admin_shift_modal.js
├── migrations/                 # Alembic骨組み
├── docs/
├── requirements.txt
├── requirements-test.txt
└── pytest.ini / pyproject.toml
```

## 互換性ポリシー

- 既存URL・画面挙動・DBスキーマは維持
- 内部実装を `App Factory + Blueprint` 構成へ移行

## 主な機能

- 認証（ユーザーID/パスワード）
- 出勤 / 退勤 / 休憩開始 / 休憩終了
- 管理画面（検索、作成、編集、削除、CSV）
- ユーザー管理
- 監査ログ（IP/UA/署名付き）

## 補足ドキュメント

- `docs/14-ゼロから再構築ガイド.md`
- `docs/13-ファイル構成.md`
- `docs/10-API・ルーティング.md`
- `docs/12-デプロイメント.md`

## Runtime Notes (2026-02)
- New environments should initialize schema with `alembic upgrade head`.
- `flask --app app init-db` is for local fallback only.
- `FLASK_DEBUG` is disabled by default. Enable it only for local development.
- `TRUST_X_FORWARDED_FOR` is disabled by default. Enable it only behind a trusted reverse proxy.
