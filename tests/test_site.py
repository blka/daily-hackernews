"""Tests for the Pages site builder."""

import re

from daily_hackernews.site import build_site, issue_date, parse_issue_date


def _issue(date: str, body: str, number: int = 1) -> dict:
    return {
        "title": f"Daily Hacker News {date}",
        "body": body,
        "html_url": f"https://github.com/blka/daily-hackernews/issues/{number}",
        "number": number,
    }


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

        index = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert "05/10/2026" in index
        assert "04/10/2026" in index
        # newest first, with link to the per-date page
        assert index.index("2026-10-05.html") < index.index("2026-10-04.html")
        # latest digest rendered in full on the index
        assert "<strong>item</strong>" in index or "<code>item</code>" in index

        page = (tmp_path / "digests" / "2026-10-05.html").read_text(encoding="utf-8")
        assert "<code>item</code>" in page
        # markdown converted, no markdown source leaked
        assert "1. First" not in page

    def test_skips_issues_without_parseable_date(self, tmp_path):
        issues = [
            {"title": "Some other issue", "body": "foo", "html_url": "x", "number": 9},
            _issue("04/10/2026", "# Daily HN"),
        ]
        build_site(issues, str(tmp_path))
        assert not (tmp_path / "digests" / "None.html").exists()
        assert (tmp_path / "digests" / "2026-10-04.html").exists()

    def test_html_escapes_issue_content(self, tmp_path):
        issues = [_issue("04/10/2026", "# Daily HN\n\n<script>alert(1)</script>")]
        build_site(issues, str(tmp_path))
        page = (tmp_path / "digests" / "2026-10-04.html").read_text(encoding="utf-8")
        assert "<script>" not in page
        assert "&lt;script&gt;" in page

    def test_html_escapes_issue_titles(self, tmp_path):
        evil = "Daily Hacker News 04/10/2026 <img src=x onerror=alert(1)>"
        issues = [{"title": evil, "body": "# Daily HN", "html_url": "x", "number": 1}]
        build_site(issues, str(tmp_path))
        page = (tmp_path / "digests" / "2026-10-04.html").read_text(encoding="utf-8")
        index = (tmp_path / "index.html").read_text(encoding="utf-8")
        for out in (page, index):
            assert "<img src=x" not in out          # no live markup
            assert "&lt;img src=x" in out            # rendered as text
            assert not re.search(r"<h1[^>]*onerror", out)
        assert "Daily Hacker News 04/10/2026" in page

    def test_strips_markdown_generated_attributes(self, tmp_path):
        # attr_list in python-markdown turns a trailing {attr} into an HTML attribute,
        # so escaping the body before conversion does not stop it.
        issues = [_issue("04/10/2026", '# Digest {onclick="alert(1)}">\n\nX')]
        build_site(issues, str(tmp_path))
        page = (tmp_path / "digests" / "2026-10-04.html").read_text(encoding="utf-8")
        # no attribute on any tag; braces survive only as plain text
        assert not re.search(r"<h[1-6][^>]*onclick", page)
        assert "<h1>Digest" in page

    def test_index_collapses_archive_below_latest(self, tmp_path):
        issues = [_issue(f"0{d}/10/2026", f"# Daily HN {d}", number=d) for d in range(1, 4)]
        build_site(issues, str(tmp_path))

        index = (tmp_path / "index.html").read_text(encoding="utf-8")
        # latest digest first, archive links after it, collapsed in <details>
        assert index.index("<h2>") < index.index("<details>")
        assert "<summary>" in index
        assert index.count("<details") == 1
        # all days linked inside the collapsed archive
        for d in range(1, 4):
            assert f"2026-10-0{d}.html" in index

    def test_duplicate_dates_keep_newest_issue(self, tmp_path):
        old = _issue("04/10/2026", "# Daily HN OLD", number=100)
        new = _issue("04/10/2026", "# Daily HN NEW", number=200)
        build_site([new, old], str(tmp_path))  # newest first on input
        page = (tmp_path / "digests" / "2026-10-04.html").read_text(encoding="utf-8")
        assert "NEW" in page
        assert "OLD" not in page


class TestIssueDateHelper:
    def test_issue_date_helper(self):
        assert issue_date("Daily Hacker News 04/10/2026") == "04/10/2026"


class TestFetchIssues:
    def test_pagination_continues_past_pr_page(self, monkeypatch):
        import daily_hackernews.site as site

        page1 = [_issue("04/10/2026", "# x", number=n) for n in range(100)]
        page1[50] = {**page1[50], "pull_request": {"url": "pr"}}  # PR inside full page
        page2 = [_issue("03/10/2026", "# y", number=n) for n in range(100, 150)]

        class FakeResp:
            def __init__(self, data):
                self.data = data

            def json(self):
                return self.data

            def raise_for_status(self):
                pass

        calls = []

        def fake_get(url, **kwargs):
            calls.append(kwargs["params"])
            return FakeResp(page1 if len(calls) == 1 else page2)

        monkeypatch.setattr(site.requests, "get", fake_get)
        result = site.fetch_issues()
        # 100 issues from page 1 (PR excluded) + 50 from page 2: no early stop
        assert len(result) == 149
        assert [c["page"] for c in calls] == [1, 2]