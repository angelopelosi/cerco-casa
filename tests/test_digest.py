from pathlib import Path
from notifier import digest

TEMPLATE = "<html><body><p>{{COUNT}} nuovi annunci</p><ul>{{LISTINGS}}</ul></body></html>"

def test_build_digest_html_with_no_listings(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text(TEMPLATE)
    html = digest.build_digest_html([], template_path=str(template_path))
    assert "Nessun nuovo annuncio" in html

def test_build_digest_html_with_listings(tmp_path):
    template_path = tmp_path / "template.html"
    template_path.write_text(TEMPLATE)
    listings = [{"titolo": "Bilocale", "comune": "Jesi", "prezzo": 500, "fonte": "subito", "url": "https://example.com/1"}]
    html = digest.build_digest_html(listings, template_path=str(template_path))
    assert "Bilocale" in html
    assert "1 nuovi annunci" in html

def test_send_digest_skips_when_no_recipients(monkeypatch):
    called = []
    monkeypatch.setattr(digest.smtplib, "SMTP_SSL", lambda *a, **k: called.append(True))
    digest.send_digest("user@example.com", "pw", [], "<html></html>")
    assert called == []

def test_send_digest_sends_via_smtp(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def login(self, user, pw): sent["login"] = (user, pw)
        def sendmail(self, from_addr, to_addrs, msg): sent["sendmail"] = (from_addr, to_addrs)

    monkeypatch.setattr(digest.smtplib, "SMTP_SSL", lambda *a, **k: FakeSMTP())
    digest.send_digest("user@example.com", "pw", ["dest@example.com"], "<html></html>")
    assert sent["login"] == ("user@example.com", "pw")
    assert sent["sendmail"][1] == ["dest@example.com"]
