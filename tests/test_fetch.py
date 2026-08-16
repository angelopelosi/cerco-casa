from pathlib import Path
from scraper.fetch import fetch_html

def test_fetch_html_returns_page_content(tmp_path):
    html_file = tmp_path / "sample.html"
    html_file.write_text("<html><body><h1 id='marker'>ciao</h1></body></html>", encoding="utf-8")

    result = fetch_html(f"file:///{html_file.as_posix()}", wait_selector="#marker", delay_ms=0)

    assert "ciao" in result
