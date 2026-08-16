from scripts import daily, weekly


def test_daily_main_calls_pipeline_in_order(monkeypatch):
    calls = []
    monkeypatch.setattr(daily, "load_dotenv", lambda: None)
    monkeypatch.setattr(daily.yaml, "safe_load", lambda text: {"portali_attivi": [], "centro": {"nome": "Jesi"}})
    monkeypatch.setattr(daily.Path, "read_text", lambda self: "")
    monkeypatch.setattr(daily, "run_all", lambda config, db_path: calls.append(("run_all", db_path)))
    monkeypatch.setattr(daily, "generate_site", lambda *a: calls.append(("generate_site", a)))
    monkeypatch.setattr(daily, "publish", lambda build_dir: calls.append(("publish", build_dir)))

    daily.daily_main()

    assert [c[0] for c in calls] == ["run_all", "generate_site", "publish"]


def test_weekly_main_calls_digest(monkeypatch):
    calls = []
    monkeypatch.setattr(weekly, "load_dotenv", lambda: None)
    monkeypatch.setattr(weekly.yaml, "safe_load", lambda text: {"email": {"destinatari": []}})
    monkeypatch.setattr(weekly.Path, "read_text", lambda self: "")
    monkeypatch.setattr(weekly.os, "environ", {"SMTP_USER": "u@example.com", "GMAIL_APP_PASSWORD": "pw"})
    monkeypatch.setattr(weekly, "run_weekly_digest", lambda db_path, config, user, pw: calls.append((db_path, user, pw)))

    weekly.weekly_main()

    assert calls == [("data/listings.db", "u@example.com", "pw")]
