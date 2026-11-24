"""Tests for the same-day duplicate guard in the digest pipeline."""

import daily_hackernews.main as pipeline


class TestDuplicateGuard:
    def test_skips_when_today_digest_exists(self, monkeypatch):
        monkeypatch.setattr(pipeline, "get_date", lambda: "24/11/2026")
        seen = {}

        def find_fake(title):
            seen["title"] = title
            return 639

        def boom(*args, **kwargs):
            raise AssertionError("must not be called when the digest already exists")

        monkeypatch.setattr(pipeline, "find_issue_by_title", find_fake)
        monkeypatch.setattr(pipeline, "fetch_stories", boom)
        monkeypatch.setattr(pipeline, "create_issue", boom)
        monkeypatch.setattr(pipeline, "lock_issue", boom)
        pipeline.main()
        assert seen["title"] == "Daily Hacker News 24/11/2026"

    def test_creates_when_no_existing(self, monkeypatch):
        monkeypatch.setattr(pipeline, "get_date", lambda: "24/11/2026")
        monkeypatch.setattr(pipeline, "find_issue_by_title", lambda title: None)
        monkeypatch.setattr(pipeline, "fetch_stories", lambda n: ["s1", "s2"])
        monkeypatch.setattr(pipeline, "render_digest", lambda stories, date: "# body")
        calls = {}

        def create_fake(title, body):
            calls["issue"] = (title, body)
            return "https://github.com/blka/daily-hackernews/issues/639"

        monkeypatch.setattr(pipeline, "create_issue", create_fake)
        monkeypatch.setattr(pipeline, "lock_issue", lambda url: calls.setdefault("lock", url) or True)
        pipeline.main()
        assert calls["issue"][0] == "Daily Hacker News 24/11/2026"
        assert calls["lock"] == "https://github.com/blka/daily-hackernews/issues/639"
