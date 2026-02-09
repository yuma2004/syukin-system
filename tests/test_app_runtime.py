from app import env_bool


def test_env_bool_returns_default_for_missing_value(monkeypatch):
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert env_bool("FLASK_DEBUG", False) is False


def test_env_bool_parses_truthy_values(monkeypatch):
    monkeypatch.setenv("FLASK_DEBUG", "true")
    assert env_bool("FLASK_DEBUG", False) is True
