"""Tests for categorizer module."""

from daily_hackernews.categorizer import Category, categorize, categorize_story
from daily_hackernews.fetcher import Story


class TestCategory:
    def test_category_values(self):
        assert Category.PROGRAMMING.value == "Programming"
        assert Category.AI_ML.value == "AI/ML"
        assert Category.SECURITY.value == "Security"
        assert Category.DEVOPS.value == "DevOps/Infra"
        assert Category.BUSINESS.value == "Business/Startups"
        assert Category.DESIGN.value == "Design/Product"
        assert Category.HARDWARE.value == "Hardware/IoT"
        assert Category.SCIENCE.value == "Science/Other"


class TestCategorizeStory:
    def test_domain_match_programming(self):
        s = Story(id=1, title="Some repo", url="https://github.com/foo/bar", domain="github.com", score=100, descendants=10, by="user")
        assert categorize_story(s) == Category.PROGRAMMING

    def test_domain_match_arxiv(self):
        s = Story(id=2, title="New model architecture", url="https://arxiv.org/abs/2401.1234", domain="arxiv.org", score=500, descendants=50, by="user")
        assert categorize_story(s) == Category.AI_ML

    def test_keyword_match_security(self):
        s = Story(id=3, title="Critical CVE in OpenSSL", url="https://example.com/cve", domain="example.com", score=300, descendants=80, by="user")
        assert categorize_story(s) == Category.SECURITY

    def test_keyword_match_case_insensitive(self):
        s = Story(id=4, title="New AI Model Released", url="https://example.com/ai", domain="example.com", score=200, descendants=30, by="user")
        assert categorize_story(s) == Category.AI_ML

    def test_domain_priority_over_keyword(self):
        """arxiv.org domain should map to AI/ML even if title has science keywords."""
        s = Story(id=5, title="Quantum computing breakthrough", url="https://arxiv.org/abs/2401.5678", domain="arxiv.org", score=400, descendants=60, by="user")
        assert categorize_story(s) == Category.AI_ML

    def test_ask_hn_falls_to_keyword(self):
        s = Story(id=6, title="Ask HN: Best Docker practices?", url=None, domain=None, score=50, descendants=20, by="user")
        assert categorize_story(s) == Category.DEVOPS

    def test_no_match_goes_to_science(self):
        s = Story(id=7, title="Unusual topic xyz", url="https://randomsite.org/article", domain="randomsite.org", score=10, descendants=2, by="user")
        assert categorize_story(s) == Category.SCIENCE

    def test_hardware_keyword(self):
        s = Story(id=8, title="New RISC-V chip announced", url="https://example.com/chip", domain="example.com", score=150, descendants=25, by="user")
        assert categorize_story(s) == Category.HARDWARE


class TestCategorize:
    def test_categorize_groups_stories(self):
        stories = [
            Story(id=1, title="Rust 2026", url="https://github.com/foo", domain="github.com", score=500, descendants=100, by="a"),
            Story(id=2, title="AI breakthrough", url="https://example.com/ai", domain="example.com", score=300, descendants=50, by="b"),
        ]
        result = categorize(stories)
        assert Category.PROGRAMMING in result
        assert Category.AI_ML in result
        assert len(result[Category.PROGRAMMING]) == 1
        assert len(result[Category.AI_ML]) == 1

    def test_categorize_empty_list(self):
        result = categorize([])
        assert result == {}