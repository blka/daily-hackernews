"""Tests for the issue publisher."""

import daily_hackernews.publisher as publisher


class TestLockIssue:
    def test_lock_issue_puts_to_api_host(self, monkeypatch):
        calls = []

        class FakeResp:
            status_code = 204

        def fake_put(url, **kwargs):
            calls.append(url)
            return FakeResp()

        monkeypatch.setattr(publisher.requests, "put", fake_put)
        monkeypatch.setenv("ACCESS_TOKEN", "tok")
        ok = publisher.lock_issue("https://github.com/blka/daily-hackernews/issues/639")
        assert ok is True
        # The lock endpoint lives on api.github.com; the web-host PUT returns
        # 422 and the lock never happens.
        assert calls == ["https://api.github.com/repos/blka/daily-hackernews/issues/639/lock"]

    def test_lock_issue_false_on_non_204(self, monkeypatch):
        class FakeResp:
            status_code = 422

        monkeypatch.setattr(publisher.requests, "put", lambda url, **kw: FakeResp())
        monkeypatch.setenv("ACCESS_TOKEN", "tok")
        assert publisher.lock_issue("https://github.com/blka/daily-hackernews/issues/639") is False

    def test_lock_issue_false_on_unparseable_url(self, monkeypatch):
        monkeypatch.setenv("ACCESS_TOKEN", "tok")
        assert publisher.lock_issue("not-a-github-issue-url") is False


class TestCreateIssue:
    def test_create_issue_requires_token(self, monkeypatch):
        monkeypatch.delenv("ACCESS_TOKEN", raising=False)
        import pytest
        with pytest.raises(RuntimeError):
            publisher.create_issue("t", "b")
