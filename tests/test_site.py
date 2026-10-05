"""Tests for the Pages site builder."""

from daily_hackernews.site import build_site, issue_date, parse_issue_date


def _issue(date: str, body: str) -> dict:
    return {"title": f"Daily Hacker News {date}", "body": body, "html_url": "https://github.com/blka/daily-hackernews/issues/1"}


class TestParseIssueDate:
    def test_parses_dd_mm_yyyy_title(self):
        assert parse_issue_date("Daily Hacker News 04/10/2026") == ("2026", "10", "04")

    def test_parses_dd_mm_yyyy_with_dashes(self):
        # Older issues used DD-MM-YYYY.
        assert parse_issue_date("Daily Hacker News 14-04-2026") == ("2026", "04", "14")

    def test_no_date_returns_none(self):
        assert parse_issue_date("Each Top Story is shown twice") is None


class TestBuildSite:
    def test_renders_index_and_per_date_pages(self, tmp_path):
        issues = [
            _issue("04/10/2026", "# Daily HN\n\n**Bold title** — [link](https://example.com)"),
            _issue("05/10/2026", "# Daily HN two\n\n1. First `item`\n2. Second item"),
        ]
        build_site(issues, str(tmp_path))

        index = (tmp_path / "index.html").read_text()
        assert "05/10/2026" in index
        assert "04/10/2026" in index
        # newest first, with link to the per-date page
        assert index.index("2026-10-05.html") < index.index("2026-10-04.html")
        # latest digest rendered in full on the index
        assert "<strong>item</strong>" in index or "<code>item</code>" in index

        page = (tmp_path / "digests" / "2026-10-05.html").read_text()
        assert "<code>item</code>" in page
        # markdown converted, no markdown source leaked
        assert "1. First" not in page

    def test_skips_issues_without_parseable_date(self, tmp_path):
        issues = [
            {"title": "Some other issue", "body": "foo", "html_url": "x"},
            _issue("04/10/2026", "# Daily HN"),
        ]
        build_site(issues, str(tmp_path))
        assert not (tmp_path / "digests" / "None.html").exists()
        assert (tmp_path / "digests" / "2026-10-04.html").exists()

    def test_html_escapes_issue_content(self, tmp_path):
        issues = [_issue("04/10/2026", "# Daily HN\n\n<script>alert(1)</script>")]
        build_site(issues, str(tmp_path))
        page = (tmp_path / "digests" / "2026-10-04.html").read_text()
        assert "<script>" not in page
        assert "&lt;script&gt;" in page

    def test_issue_date_helper(self):
        assert issue_date("Daily Hacker News 04/10/2026") == "04/10/2026"