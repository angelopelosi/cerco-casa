import pytest
from scripts import publish as publish_module

def test_publish_raises_if_build_dir_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        publish_module.publish(build_dir="webapp/build")

def test_publish_skips_commit_when_no_changes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "webapp" / "build").mkdir(parents=True)
    calls = []

    def fake_run(cmd, check=False, **kwargs):
        calls.append(cmd)
        class Result:
            returncode = 0
        return Result()

    monkeypatch.setattr(publish_module.subprocess, "run", fake_run)
    publish_module.publish(build_dir="webapp/build")

    assert any(c[:2] == ["git", "diff"] for c in calls)
    assert not any(c[:2] == ["git", "commit"] for c in calls)
    assert "nessuna modifica" in capsys.readouterr().out

def test_publish_commits_and_pushes_when_changed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "webapp" / "build").mkdir(parents=True)
    calls = []

    def fake_run(cmd, check=False, **kwargs):
        calls.append(cmd)
        class Result:
            returncode = 1 if cmd[:2] == ["git", "diff"] else 0
        return Result()

    monkeypatch.setattr(publish_module.subprocess, "run", fake_run)
    publish_module.publish(build_dir="webapp/build", branch="gh-pages")

    assert any(c[:2] == ["git", "commit"] for c in calls)
    assert any("subtree" in c for c in calls)
