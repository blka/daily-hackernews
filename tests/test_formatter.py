"""Tests for formatter module."""

from daily_hackernews.fetcher import Story
from daily_hackernews.categorizer import Category
from daily_hackernews.formatter import format_score, render_digest


class TestFormatScore:
    def test_regular_score(self):
        assert format_score(850) == "850"

    def test_thousand_score(self):
        assert format_score(1200) == "1.2k"

    def test_large_score(self):
        assert format_score(5400) == "5.4k"

    def test_zero_score(self):
        assert format_score(0) == "0"

    def test_exact_thousand(self):
        assert format_score(1000) == "1.0k"


class TestRenderDigest:
    def test_renders_header_with_date(self):
        stories = [
            Story(id=1, title="Test story", url="https://example.com", domain="example.com", score=100, descendants=10, by="user")
        ]
        result = render_digest(stories, date="13/06/2026")
        assert "Daily Hacker News — 13/06/2026" in result

    def test_no_top_stories_section(self):
        stories = [
            Story(id=1, title="Top story", url="https://example.com", domain="example.com", score=500, descendants=50, by="user"),
            Story(id=2, title="Low story", url="https://other.com", domain="other.com", score=10, descendants=1, by="user"),
        ]
        result = render_digest(stories, date="13/06/2026")
        assert "Top story" in result
        assert "Top Stories" not in result

    def test_top_five_stories_get_fire_marker(self):
        stories = [
            Story(id=i, title=f"Story {i}", url="https://github.com/rust", domain="github.com", score=600 - i, descendants=10, by="user")
            for i in range(1, 7)
        ]
        result = render_digest(stories, date="13/06/2026")
        assert result.count("🔥") == 5

    def test_low_score_story_has_no_fire_marker(self):
        stories = [
            Story(id=i, title=f"Story {i}", url="https://github.com/rust", domain="github.com", score=600 - i, descendants=10, by="user")
            for i in range(1, 6)
        ]
        stories.append(
            Story(id=6, title="Cold story", url="https://other.com", domain="other.com", score=10, descendants=1, by="user")
        )
        result = render_digest(stories, date="13/06/2026")
        assert result.count("🔥") == 5
        assert "🔥 [Cold story]" not in result

    def test_fewer_than_five_stories_all_marked(self):
        stories = [
            Story(id=i, title=f"Story {i}", url="https://github.com/rust", domain="github.com", score=100 - i, descendants=10, by="user")
            for i in range(1, 4)
        ]
        result = render_digest(stories, date="13/06/2026")
        assert result.count("🔥") == 3

    def test_renders_category_sections(self):
        stories = [
            Story(id=1, title="Rust release", url="https://github.com/rust", domain="github.com", score=300, descendants=30, by="user"),
        ]
        result = render_digest(stories, date="13/06/2026")
        assert "💻 Programming" in result

    def test_self_post_title_links_to_hn_item(self):
        stories = [
            Story(id=1, title="Tell HN: Something", url=None, domain=None, score=500, descendants=20, by="user"),
        ]
        result = render_digest(stories, date="13/06/2026")
        # Self-post has no URL — the title links to the HN item itself.
        assert "[Tell HN: Something](https://news.ycombinator.com/item?id=1)" in result
        # And the 💬 comment link is not duplicated next to it.
        assert "[💬 20](https://news.ycombinator.com/item?id=1)" not in result
        # Meta line has no dangling leading separator when domain is absent.
        meta = next(l for l in result.split("\n") if "⭐ 500" in l)
        assert meta.lstrip().startswith("⭐")

    def test_renders_ask_hn(self):
        stories = [
            Story(id=1, title="Ask HN: Something", url=None, domain=None, score=50, descendants=20, by="user"),
        ]
        result = render_digest(stories, date="13/06/2026")
        assert "Ask HN: Something" in result
        # Ask HN should not have [Article] link
        lines = result.split("\n")
        ask_hn_lines = [l for l in lines if "Ask HN" in l and "Comments" not in l]
        for line in ask_hn_lines:
            assert "[Article]" not in line

    def test_daily_stats_line(self):
        stories = [
            Story(id=1, title="A", url="https://example.com", domain="example.com", score=100, descendants=10, by="user"),
        ]
        result = render_digest(stories, date="13/06/2026")
        assert "1 stories" in result
        assert "avg score: 100" in result

    def test_formatted_score_in_output(self):
        stories = [
            Story(id=1, title="Big story", url="https://github.com/rust", domain="github.com", score=1200, descendants=100, by="user"),
        ]
        result = render_digest(stories, date="13/06/2026")
        assert "1.2k" in result

    def test_render_digest_has_card_layout(self):
        # Five fillers keep "Test Story" outside the top-5 so the card
        # layout is asserted without the 🔥 top-story marker.
        stories = [
            Story(id=i, title=f"Filler {i}", score=500, descendants=5, url="http://filler.com", domain="github.com", by="user")
            for i in range(2, 7)
        ]
        stories.append(
            Story(id=1, title="Test Story", score=10, descendants=5, url="http://test.com", domain="test.com", by="user")
        )
        output = render_digest(stories, date="2026-07-09")

        assert "**[Test Story](http://test.com)**" in output
        assert "`test.com` · ⭐ 10 · [💬 5]" in output
        # Item separators are gone; only `---` between sections remains.
        assert "***" not in output
        assert "---" in output
