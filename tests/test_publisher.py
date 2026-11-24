"""Tests for the issue publisher."""

import daily_hackernews.publisher as publisher


def _issue(number: int, title: str = "Daily Hacker News 24/11/2026", pr: bool = False):
    issue = {
        "number": number,
        "title": title,
        "html_url": f"https://github.com/blka/daily-hackernews/issues/{number}",
        "body": "x",
    }
    if pr:
        issue["pull_request"] = {"url": "pr"}
    return issue


class _FakeResp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status
        self.text = f"status {status}"

    def json(self):
        return self._data


class TestFindIssueByTitle:
    def test_found_returns_number(self, monkeypatch):
        calls = []

        def fake_get(url, **kwargs):
            calls.append(kwargs["params"])
            return _FakeResp([_issue(100, title="Daily Hacker News 24/11/2026"), _issue(101, title="Old")])

        monkeypatch.setattr(publisher.requests, "get", fake_get)
        monkeypatch.setenv("ACCESS_TOKEN", "tok")
        assert publisher.find_issue_by_title("Daily Hacker News 24/11/2026") == 100
        assert calls[0]["page"] == 1 and calls[0]["labels"] == "daily-digest"

    def test_not_found_returns_none(self, monkeypatch):
        monkeypatch.setattr(publisher.requests, "get", lambda url, **kw: _FakeResp([_issue(2, title="Other")]))
        monkeypatch.setenv("ACCESS_TOKEN", "tok")
        assert publisher.find_issue_by_title("Daily Hacker News 24/11/2026") is None

    def test_prs_do_not_truncate_pages(self, monkeypatch):
        # page 1: 99 PRs + the match as issue 100 — raw length stays 100
        page1 = [_issue(900 + i, title=f"PR {i}", pr=True) for i in range(99)]
        page1.append(_issue(639, title="Daily Hacker News 24/11/2026"))
        calls = []

        def fake_get(url, **kwargs):
            calls.append(kwargs["params"]["page"])
            return _FakeResp(page1)

        monkeypatch.setattr(publisher.requests, "get", fake_get)
        monkeypatch.setenv("ACCESS_TOKEN", "tok")
        assert publisher.find_issue_by_title("Daily Hacker News 24/11/2026") == 639
        assert calls == [1]

    def test_non_200_raises(self, monkeypatch):
        monkeypatch.setattr(publisher.requests, "get", lambda url, **kw: _FakeResp([], status=500))
        monkeypatch.setenv("ACCESS_TOKEN", "tok")
        import pytest
        with pytest.raises(RuntimeError):
            publisher.find_issue_by_title("Daily Hacker News 24/11/2026")

    def test_requires_token(self, monkeypatch):
        monkeypatch.delenv("ACCESS_TOKEN", raising=False)
        import pytest
        with pytest.raises(RuntimeError):
            publisher.find_issue_by_title("Daily Hacker News 24/11/2026")


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
