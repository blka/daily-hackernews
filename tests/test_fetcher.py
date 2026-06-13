"""Tests for fetcher module."""

from daily_hackernews.fetcher import Story, _extract_domain


class TestExtractDomain:
    def test_https_url(self):
        assert _extract_domain("https://blog.rust-lang.org/post") == "blog.rust-lang.org"

    def test_http_url(self):
        assert _extract_domain("http://example.com/path") == "example.com"

    def test_complex_domain(self):
        assert _extract_domain("https://docs.python.org/3/library/abc.html") == "docs.python.org"


class TestStory:
    def test_story_fields(self, sample_story):
        assert sample_story.id == 12345
        assert sample_story.title == "Rust 2026 Edition Released"
        assert sample_story.url == "https://blog.rust-lang.org/2026/rust-2026.html"
        assert sample_story.domain == "blog.rust-lang.org"
        assert sample_story.score == 850
        assert sample_story.descendants == 342

    def test_ask_hn_has_no_url(self, ask_hn_story):
        assert ask_hn_story.url is None
        assert ask_hn_story.domain is None

    def test_story_defaults(self):
        s = Story(id=1, title="test", url=None, domain=None, score=0, descendants=0, by="x")
        assert s.score == 0
        assert s.descendants == 0