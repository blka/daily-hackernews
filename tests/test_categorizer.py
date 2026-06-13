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

    def test_security_keyword_surveillance(self):
        s = Story(id=9, title="Surveillance is not safety", url="https://signal.org/blog", domain="signal.org", score=690, descendants=340, by="user")
        assert categorize_story(s) == Category.SECURITY

    def test_security_keyword_certificate(self):
        s = Story(id=10, title="Let's Encrypt bans certificate usage", url="https://letsencrypt.org/docs", domain="letsencrypt.org", score=454, descendants=380, by="user")
        assert categorize_story(s) == Category.SECURITY

    def test_ai_keyword_diffusion(self):
        s = Story(id=11, title="DiffusionGemma: 4x Faster Text Generation", url="https://blog.google/ai", domain="blog.google", score=325, descendants=87, by="user")
        assert categorize_story(s) == Category.AI_ML

    def test_programming_keyword_emacs(self):
        s = Story(id=12, title="Emacs appearances in pop culture", url="https://example.com/emacs", domain="example.com", score=402, descendants=116, by="user")
        assert categorize_story(s) == Category.PROGRAMMING

    def test_devops_keyword_chrome(self):
        s = Story(id=13, title="Chrome is looking to permanently drop MV2 extension", url="https://neowin.net/article", domain="neowin.net", score=412, descendants=440, by="user")
        assert categorize_story(s) == Category.DEVOPS

    def test_devops_domain_pgdog(self):
        s = Story(id=14, title="PgDog is funded and coming", url="https://pgdog.dev/blog", domain="pgdog.dev", score=541, descendants=259, by="user")
        # pgdog.dev not in domain map, "funded" not a keyword — falls to Science/Other
        assert categorize_story(s) == Category.SCIENCE

    def test_business_keyword_datacenter(self):
        s = Story(id=15, title="Farmer donates land, city sells for data center", url="https://example.com/dc", domain="example.com", score=474, descendants=3, by="user")
        assert categorize_story(s) == Category.BUSINESS

    def test_hardware_keyword_motor(self):
        s = Story(id=16, title="Mercedes starts production of electric axial flux motor", url="https://example.com/motor", domain="example.com", score=544, descendants=350, by="user")
        assert categorize_story(s) == Category.HARDWARE

    def test_security_domain_signal(self):
        s = Story(id=17, title="Some signal post", url="https://signal.org/blog/post", domain="signal.org", score=100, descendants=10, by="user")
        assert categorize_story(s) == Category.SECURITY

    def test_ai_domain_blog_google(self):
        s = Story(id=18, title="Google AI announcement", url="https://blog.google/innovation/ai/", domain="blog.google", score=200, descendants=20, by="user")
        assert categorize_story(s) == Category.AI_ML


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