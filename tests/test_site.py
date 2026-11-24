"""Tests for the Pages site builder."""

import re

from daily_hackernews.site import (
    build_incremental,
    build_site,
    issue_date,
    load_manifest,
    parse_issue_date,
)


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


class TestManifest:
    def _manifest(self, tmp_path):
        import json
        return json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))

    def test_full_build_writes_manifest(self, tmp_path):
        issues = [_issue("05/10/2026", "# a", number=2), _issue("04/10/2026", "# b", number=1)]
        build_site(issues, str(tmp_path))
        data = self._manifest(tmp_path)
        assert [e["date"] for e in data["pages"]] == ["2026-10-05", "2026-10-04"]
        entry = data["pages"][0]
        assert entry == {
            "page_path": "digests/2026-10-05.html",
            "number": 2,
            "title": "Daily Hacker News 05/10/2026",
            "date": "2026-10-05",
            "body": "# a",
        }

    def test_full_build_dedup_kept_in_manifest(self, tmp_path):
        issues = [_issue("04/10/2026", "# OLD", number=100), _issue("04/10/2026", "# NEW", number=200)]
        build_site(issues, str(tmp_path))
        assert len(self._manifest(tmp_path)["pages"]) == 1
        assert self._manifest(tmp_path)["pages"][0]["number"] == 200

    def test_load_manifest_roundtrip(self, tmp_path):
        issues = [_issue("04/10/2026", "# b", number=1)]
        build_site(issues, str(tmp_path))
        assert load_manifest(str(tmp_path)) == self._manifest(tmp_path)["pages"]

    def test_load_manifest_returns_none_on_missing(self, tmp_path):
        assert load_manifest(str(tmp_path)) is None

    def test_load_manifest_returns_none_on_corrupt(self, tmp_path):
        (tmp_path / "manifest.json").write_text("not json{", encoding="utf-8")
        assert load_manifest(str(tmp_path)) is None

    def test_load_manifest_returns_none_on_bad_entries(self, tmp_path):
        (tmp_path / "manifest.json").write_text('{"pages": [{"page_path": "x"}]}', encoding="utf-8")
        assert load_manifest(str(tmp_path)) is None
        (tmp_path / "manifest.json").write_text(
            '{"pages": [{"page_path": "a", "number": 1, "title": "t", "date": "2026-10-04", "body": "b"},'
            '{"page_path": "c", "number": 1, "title": "t", "date": "2026-10-04", "body": "b"}]}',
            encoding="utf-8")
        assert load_manifest(str(tmp_path)) is None  # duplicate dates


class TestFetchAuth:
    def _resp(self, data, status=200, headers=None):
        import requests

        class R:
            def __init__(self):
                self.status_code = status
                self.headers = headers or {}

            def json(self):
                return data

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise requests.exceptions.HTTPError(
                        f"{self.status_code}",
                        response=type("X", (), {"status_code": self.status_code})(),
                    )

        return R()

    def test_token_sends_authorization_header(self, monkeypatch):
        import daily_hackernews.site as site

        seen = {}

        def fake_get(url, **kwargs):
            seen.update(kwargs)
            return self._resp([])

        monkeypatch.setattr(site.requests, "get", fake_get)
        site.fetch_issues(token="T0K3N")
        assert seen["headers"]["Authorization"] == "Bearer T0K3N"

    def test_no_token_omits_authorization(self, monkeypatch):
        import daily_hackernews.site as site

        seen = {}

        def fake_get(url, **kwargs):
            seen.update(kwargs)
            return self._resp([])

        monkeypatch.setattr(site.requests, "get", fake_get)
        site.fetch_issues()
        assert "Authorization" not in seen["headers"]

    def test_retry_on_rate_limit_then_success(self, monkeypatch):
        import daily_hackernews.site as site

        issues = [_issue("01/10/2026", "# x", number=n) for n in range(50)]
        calls, sleeps = [], []

        def fake_get(url, **kwargs):
            calls.append(1)
            return self._resp([], status=403) if len(calls) == 1 else self._resp(issues)

        monkeypatch.setattr(site.requests, "get", fake_get)
        monkeypatch.setattr(site.time, "sleep", sleeps.append)
        result = site.fetch_issues(token="T")
        assert len(calls) == 2 and len(sleeps) == 1 and len(result) == 50

    def test_limited_retry_then_loud_failure(self, monkeypatch):
        import pytest
        import daily_hackernews.site as site

        calls, sleeps = [], []

        def fake_get(url, **kwargs):
            calls.append(1)
            return self._resp([], status=403)

        monkeypatch.setattr(site.requests, "get", fake_get)
        monkeypatch.setattr(site.time, "sleep", sleeps.append)
        with pytest.raises(Exception):
            site.fetch_issues(token="T")
        assert len(calls) == 4 and len(sleeps) == 3


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

    def test_early_stop_reduces_pages(self, monkeypatch):
        import daily_hackernews.site as site

        page1 = [_issue("05/10/2026", "# x", number=n) for n in range(300, 200, -1)]
        page2 = [_issue("04/10/2026", "# y", number=n) for n in range(200, 100, -1)]
        calls = []

        def fake_get(url, **kwargs):
            calls.append(kwargs["params"]["page"])

            class FakeResp:
                def json(self):
                    return page1 if kwargs["params"]["page"] == 1 else page2

                def raise_for_status(self):
                    pass

            return FakeResp()

        monkeypatch.setattr(site.requests, "get", fake_get)
        result = site.fetch_issues(stop_below=150)
        assert calls == [1, 2]
        assert {i["number"] for i in result} == set(range(101, 301))

    def test_no_early_stop_when_none(self, monkeypatch):
        import daily_hackernews.site as site

        page1 = [_issue("05/10/2026", "# x", number=n) for n in range(300, 200, -1)]
        page2 = [_issue("04/10/2026", "# y", number=n) for n in range(200, 101, -1)]  # 99 < 100
        calls = []

        def fake_get(url, **kwargs):
            calls.append(kwargs["params"]["page"])

            class FakeResp:
                def json(self):
                    return page1 if kwargs["params"]["page"] == 1 else page2

                def raise_for_status(self):
                    pass

            return FakeResp()

        monkeypatch.setattr(site.requests, "get", fake_get)
        site.fetch_issues()
        assert calls == [1, 2]  # without stop_below, everything is paged

    def test_early_stop_counts_raw_page_with_pr(self, monkeypatch):
        import daily_hackernews.site as site

        calls = []
        pr_page = [{"number": 99, "title": "PR", "pull_request": {"url": "x"}}]

        def fake_get(url, **kwargs):
            calls.append(1)

            class FakeResp:
                def json(self):
                    return pr_page

                def raise_for_status(self):
                    pass

            return FakeResp()

        monkeypatch.setattr(site.requests, "get", fake_get)
        result = site.fetch_issues(stop_below=150)
        assert len(calls) == 1  # raw page shorter than 100 → stop, no page 2
        assert result == []


class TestIncremental:
    def _entries(self, tmp_path):
        import json
        return json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["pages"]

    def test_new_date_adds_page_and_manifest_entry(self, tmp_path):
        build_site([_issue("04/10/2026", "old digest text", number=100)], str(tmp_path))
        build_incremental([_issue("05/10/2026", "new digest text", number=200)], self._entries(tmp_path), str(tmp_path))
        assert "new digest text" in (tmp_path / "digests" / "2026-10-05.html").read_text(encoding="utf-8")
        entries = self._entries(tmp_path)
        assert len(entries) == 2
        assert entries[0]["date"] == "2026-10-05"  # newest first

    def test_same_date_newer_number_overrides_manifest(self, tmp_path):
        build_site([_issue("04/10/2026", "old digest text", number=100)], str(tmp_path))
        build_incremental([_issue("04/10/2026", "new digest text", number=200)], self._entries(tmp_path), str(tmp_path))
        page = (tmp_path / "digests" / "2026-10-04.html").read_text(encoding="utf-8")
        assert "new digest text" in page and "old digest text" not in page
        assert self._entries(tmp_path)[0]["number"] == 200

    def test_below_manifest_number_issue_is_skipped(self, tmp_path):
        build_site([_issue("05/10/2026", "alpha digest", number=10), _issue("04/10/2026", "bee digest", number=100)], str(tmp_path))
        build_incremental([_issue("04/10/2026", "dup digest", number=50)], self._entries(tmp_path), str(tmp_path))
        page = (tmp_path / "digests" / "2026-10-04.html").read_text(encoding="utf-8")
        assert "bee digest" in page and "dup digest" not in page
        assert len(self._entries(tmp_path)) == 2

    def test_index_rebuilt_from_manifest_plus_new(self, tmp_path):
        build_site([_issue("04/10/2026", "old digest text", number=100)], str(tmp_path))
        build_incremental([_issue("05/10/2026", "new digest text", number=200)], self._entries(tmp_path), str(tmp_path))
        index = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert "05/10/2026" in index and "04/10/2026" in index
        assert index.index("2026-10-05.html") < index.index("2026-10-04.html")
        assert "new digest text" in index  # latest digest body on index
        assert index.count("<details") == 1


class TestMainFlow:
    def test_full_rebuild_when_no_manifest(self, tmp_path, monkeypatch):
        import daily_hackernews.site as site

        seen = {}

        def fake_fetch(token=None, stop_below=None):
            seen["stop_below"] = stop_below
            return [_issue("04/10/2026", "digest text", number=1)]

        monkeypatch.setattr(site, "fetch_issues", fake_fetch)
        site.main(str(tmp_path))
        assert seen["stop_below"] is None           # full path: no early stop
        assert (tmp_path / "manifest.json").exists()

    def test_incremental_run_uses_manifest(self, tmp_path, monkeypatch):
        import daily_hackernews.site as site

        monkeypatch.setattr(site, "fetch_issues", lambda token=None, stop_below=None: [_issue("04/10/2026", "day one", number=1)])
        site.main(str(tmp_path))                    # full build seeds manifest + pages
        before = (tmp_path / "digests" / "2026-10-04.html").read_bytes()
        captured = {}

        def fake_fetch2(token=None, stop_below=None):
            captured["stop_below"] = stop_below
            return [_issue("05/10/2026", "day two", number=2)]

        monkeypatch.setattr(site, "fetch_issues", fake_fetch2)
        site.main(str(tmp_path))
        assert captured["stop_below"] == 1          # oldest manifest number
        assert (tmp_path / "digests" / "2026-10-05.html").exists()
        assert (tmp_path / "digests" / "2026-10-04.html").read_bytes() == before  # old page untouched
        assert (tmp_path / "index.html").read_text(encoding="utf-8").count("2026-10-04.html") >= 1

    def test_main_falls_back_to_full_rebuild(self, tmp_path, monkeypatch):
        import daily_hackernews.site as site

        (tmp_path / "manifest.json").write_text("garbage", encoding="utf-8")
        seen = {}

        def fake_fetch(token=None, stop_below=None):
            seen["stop_below"] = stop_below
            return [_issue("04/10/2026", "digest text", number=1)]

        monkeypatch.setattr(site, "fetch_issues", fake_fetch)
        site.main(str(tmp_path))
        assert seen["stop_below"] is None

    def test_main_falls_back_when_page_files_missing(self, tmp_path, monkeypatch):
        import daily_hackernews.site as site

        monkeypatch.setattr(site, "fetch_issues", lambda token=None, stop_below=None: [_issue("04/10/2026", "digest text", number=1)])
        site.main(str(tmp_path))
        (tmp_path / "digests" / "2026-10-04.html").unlink()
        seen = {}

        def fake_fetch2(token=None, stop_below=None):
            seen["stop_below"] = stop_below
            return []

        monkeypatch.setattr(site, "fetch_issues", fake_fetch2)
        site.main(str(tmp_path))
        assert seen["stop_below"] is None