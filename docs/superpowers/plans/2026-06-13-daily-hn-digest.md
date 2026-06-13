# Daily HackerNews Digest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the Daily HackerNews script into a modular pipeline that produces categorized, formatted GitHub Issues with top stories highlights and daily stats.

**Architecture:** Pipeline pattern — fetcher pulls stories from HN API, categorizer groups them by domain/keyword heuristics, formatter renders Markdown via Jinja2 templates, publisher creates and locks the GitHub Issue. Each module is a single file with a single responsibility.

**Tech Stack:** Python 3.10, requests, jinja2, certifi, pytest (dev)

---

## File Structure

| File | Purpose |
|---|---|
| `daily_hackernews/__init__.py` | Package init |
| `daily_hackernews/fetcher.py` | HN API client, `Story` dataclass |
| `daily_hackernews/categorizer.py` | Domain/keyword heuristics, `Category` enum |
| `daily_hackernews/formatter.py` | Jinja2 template rendering, score formatting helpers |
| `daily_hackernews/publisher.py` | GitHub Issues REST API client |
| `daily_hackernews/main.py` | Pipeline orchestrator |
| `daily_hackernews/templates/digest.md.j2` | Jinja2 template for issue body |
| `tests/test_fetcher.py` | Fetcher unit tests |
| `tests/test_categorizer.py` | Categorizer unit tests |
| `tests/test_formatter.py` | Formatter unit tests |
| `tests/conftest.py` | Shared fixtures |
| `requirements.txt` | Production dependencies (updated) |
| `requirements-dev.txt` | Dev/test dependencies |
| `main.py` | Entry point (updated to import from package) |

Old files `hacker_news.py` and `issue.py` are replaced by the package and deleted.

---

### Task 1: Project structure and Story dataclass

**Files:**
- Create: `daily_hackernews/__init__.py`
- Create: `daily_hackernews/fetcher.py`
- Create: `tests/conftest.py`
- Create: `tests/test_fetcher.py`

- [ ] **Step 1: Create package directory and `__init__.py`**

```bash
mkdir -p daily_hackernews
touch daily_hackernews/__init__.py
```

- [ ] **Step 2: Write `daily_hackernews/fetcher.py` with `Story` dataclass and stub functions**

```python
"""HN API client — fetch top stories and their details."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import certifi
import requests

HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"


@dataclass
class Story:
    id: int
    title: str
    url: str | None
    domain: str | None
    score: int
    descendants: int
    by: str


def _extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    m = re.search(r"https?://([A-Za-z_0-9.-]+)", url)
    return m.group(1) if m else url


def get_top_story_ids(count: int = 25) -> list[int]:
    """Fetch top story IDs from HN API."""
    resp = requests.get(HN_TOP_STORIES_URL, verify=certifi.where(), timeout=30)
    resp.raise_for_status()
    all_ids = json.loads(resp.text)
    return all_ids[:count]


def get_story(item_id: int) -> Story:
    """Fetch a single story by ID and return a Story dataclass."""
    resp = requests.get(
        HN_ITEM_URL.format(item_id), verify=certifi.where(), timeout=30
    )
    resp.raise_for_status()
    data = json.loads(resp.text)
    url = data.get("url")
    return Story(
        id=data["id"],
        title=data.get("title", ""),
        url=url,
        domain=_extract_domain(url) if url else None,
        score=data.get("score", 0),
        descendants=data.get("descendants", 0),
        by=data.get("by", ""),
    )


def fetch_stories(count: int = 25) -> list[Story]:
    """Fetch top `count` stories from HN."""
    ids = get_top_story_ids(count)
    return [get_story(id_) for id_ in ids]
```

- [ ] **Step 3: Create `tests/conftest.py` with shared fixtures**

```python
"""Shared test fixtures."""

import pytest
from daily_hackernews.fetcher import Story


@pytest.fixture
def sample_story() -> Story:
    return Story(
        id=12345,
        title="Rust 2026 Edition Released",
        url="https://blog.rust-lang.org/2026/rust-2026.html",
        domain="blog.rust-lang.org",
        score=850,
        descendants=342,
        by="rustacean",
    )


@pytest.fixture
def ask_hn_story() -> Story:
    return Story(
        id=67890,
        title="Ask HN: Best practices for microservices?",
        url=None,
        domain=None,
        score=120,
        descendants=89,
        by="curious_dev",
    )
```

- [ ] **Step 4: Write `tests/test_fetcher.py`**

```python
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
```

- [ ] **Step 5: Install pytest and run tests**

```bash
pip install pytest
python -m pytest tests/test_fetcher.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add daily_hackernews/ tests/conftest.py tests/test_fetcher.py
git commit -m "feat: add Story dataclass and fetcher module with tests"
```

---

### Task 2: Categorizer

**Files:**
- Create: `daily_hackernews/categorizer.py`
- Create: `tests/test_categorizer.py`

- [ ] **Step 1: Write `tests/test_categorizer.py` with failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_categorizer.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'daily_hackernews.categorizer'`

- [ ] **Step 3: Write `daily_hackernews/categorizer.py`**

```python
"""Categorize HN stories by domain and keyword heuristics."""

from __future__ import annotations

from enum import Enum
from collections import defaultdict

from daily_hackernews.fetcher import Story


class Category(Enum):
    PROGRAMMING = "Programming"
    AI_ML = "AI/ML"
    SECURITY = "Security"
    DEVOPS = "DevOps/Infra"
    BUSINESS = "Business/Startups"
    DESIGN = "Design/Product"
    HARDWARE = "Hardware/IoT"
    SCIENCE = "Science/Other"


# Domain → Category (first match wins)
DOMAIN_MAP: dict[str, Category] = {
    "github.com": Category.PROGRAMMING,
    "gitlab.com": Category.PROGRAMMING,
    "stackoverflow.com": Category.PROGRAMMING,
    "docs.python.org": Category.PROGRAMMING,
    "docs.rs": Category.PROGRAMMING,
    "arxiv.org": Category.AI_ML,
    "openai.com": Category.AI_ML,
    "deepmind.com": Category.AI_ML,
    "huggingface.co": Category.AI_ML,
    "krebsonsecurity.com": Category.SECURITY,
    "schneier.com": Category.SECURITY,
    "thehackernews.com": Category.SECURITY,
    "docker.com": Category.DEVOPS,
    "kubernetes.io": Category.DEVOPS,
    "hashicorp.com": Category.DEVOPS,
    "techcrunch.com": Category.BUSINESS,
    "ycombinator.com": Category.BUSINESS,
    "crunchbase.com": Category.BUSINESS,
    "figma.com": Category.DESIGN,
    "medium.com": Category.DESIGN,
    "uxdesign.cc": Category.DESIGN,
    "nature.com": Category.SCIENCE,
    "sciencedirect.com": Category.SCIENCE,
}

# Keyword → Category (case-insensitive match in title)
KEYWORD_MAP: dict[str, Category] = {
    # Programming
    "python": Category.PROGRAMMING,
    "rust": Category.PROGRAMMING,
    "javascript": Category.PROGRAMMING,
    "typescript": Category.PROGRAMMING,
    "compiler": Category.PROGRAMMING,
    "language": Category.PROGRAMMING,
    "framework": Category.PROGRAMMING,
    "library": Category.PROGRAMMING,
    "programming": Category.PROGRAMMING,
    "code": Category.PROGRAMMING,
    "developer": Category.PROGRAMMING,
    # AI/ML
    "AI": Category.AI_ML,
    "LLM": Category.AI_ML,
    "GPT": Category.AI_ML,
    "neural": Category.AI_ML,
    "machine learning": Category.AI_ML,
    "transformer": Category.AI_ML,
    "deep learning": Category.AI_ML,
    "model": Category.AI_ML,
    "chatbot": Category.AI_ML,
    # Security
    "vulnerability": Category.SECURITY,
    "CVE": Category.SECURITY,
    "exploit": Category.SECURITY,
    "breach": Category.SECURITY,
    "hack": Category.SECURITY,
    "security": Category.SECURITY,
    "ransomware": Category.SECURITY,
    "malware": Category.SECURITY,
    # DevOps/Infra
    "kubernetes": Category.DEVOPS,
    "docker": Category.DEVOPS,
    "container": Category.DEVOPS,
    "cloud": Category.DEVOPS,
    "terraform": Category.DEVOPS,
    "CI/CD": Category.DEVOPS,
    "deploy": Category.DEVOPS,
    "infrastructure": Category.DEVOPS,
    "serverless": Category.DEVOPS,
    # Business/Startups
    "startup": Category.BUSINESS,
    "VC": Category.BUSINESS,
    "funding": Category.BUSINESS,
    "IPO": Category.BUSINESS,
    "revenue": Category.BUSINESS,
    "founder": Category.BUSINESS,
    "SaaS": Category.BUSINESS,
    "enterprise": Category.BUSINESS,
    # Design/Product
    "UX": Category.DESIGN,
    "UI": Category.DESIGN,
    "design": Category.DESIGN,
    "product": Category.DESIGN,
    "interface": Category.DESIGN,
    "usability": Category.DESIGN,
    "accessibility": Category.DESIGN,
    # Hardware/IoT
    "hardware": Category.HARDWARE,
    "chip": Category.HARDWARE,
    "CPU": Category.HARDWARE,
    "GPU": Category.HARDWARE,
    "embedded": Category.HARDWARE,
    "IoT": Category.HARDWARE,
    "Raspberry": Category.HARDWARE,
    "FPGA": Category.HARDWARE,
    "semiconductor": Category.HARDWARE,
    # Science/Other
    "quantum": Category.SCIENCE,
    "physics": Category.SCIENCE,
    "biology": Category.SCIENCE,
    "research": Category.SCIENCE,
    "science": Category.SCIENCE,
    "space": Category.SCIENCE,
    "climate": Category.SCIENCE,
}


def categorize_story(story: Story) -> Category:
    """Assign a category to a single story. Domain match takes priority over keyword."""
    # 1. Domain match
    if story.domain and story.domain in DOMAIN_MAP:
        return DOMAIN_MAP[story.domain]

    # 2. Keyword match (case-insensitive)
    title_lower = story.title.lower()
    for keyword, category in KEYWORD_MAP.items():
        if keyword.lower() in title_lower:
            return category

    # 3. No match
    return Category.SCIENCE


def categorize(stories: list[Story]) -> dict[Category, list[Story]]:
    """Group stories into categories. Empty categories are omitted."""
    groups: dict[Category, list[Story]] = defaultdict(list)
    for story in stories:
        cat = categorize_story(story)
        groups[cat].append(story)
    return dict(groups)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_categorizer.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add daily_hackernews/categorizer.py tests/test_categorizer.py
git commit -m "feat: add categorizer with domain/keyword heuristics and tests"
```

---

### Task 3: Formatter with Jinja2 template

**Files:**
- Create: `daily_hackernews/templates/digest.md.j2`
- Create: `daily_hackernews/formatter.py`
- Create: `tests/test_formatter.py`

- [ ] **Step 1: Add jinja2 to requirements**

Update `requirements.txt`:

```
certifi==2026.5.20
charset-normalizer==3.4.6
idna==3.16
jinja2>=3.1
mdutils==1.8.1
requests==2.34.2
urllib3==2.7.0
```

And create `requirements-dev.txt`:

```
pytest>=7.0
```

- [ ] **Step 2: Create `daily_hackernews/templates/digest.md.j2`**

```jinja2
# Daily Hacker News — {{ date }}

> **Daily Stats:** {{ stories | length }} stories · avg score: {{ avg_score }} · top domain: {{ top_domain }}

## 🔥 Top Stories

{% for story in top_stories %}
{{ loop.index }}. **{{ story.title }}** {% if story.domain %}`{{ story.domain }}`{% endif %} — ⭐ {{ story.score | fmt_score }} · 💬 {{ story.descendants }}
   {% if story.url %}[Article]({{ story.url }}) · {% endif %}[Comments](https://news.ycombinator.com/item?id={{ story.id }})
{% endfor %}

---

{% for cat in categories %}
## {{ cat.emoji }} {{ cat.value }}

| # | Title | Domain | Score | Comments |
|---|---|---|---|---|
{% for story in cat_stories[cat] %}
| {{ loop.index }} | {% if story.url %}[{{ story.title }}]({{ story.url }}){% else %}{{ story.title }}{% endif %} | {% if story.domain %}{{ story.domain }}{% else %}—{% endif %} | {{ story.score | fmt_score }} | [💬 {{ story.descendants }}](https://news.ycombinator.com/item?id={{ story.id }}) |
{% endfor %}

---

{% endfor %}
```

- [ ] **Step 3: Write `tests/test_formatter.py` with failing tests**

```python
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

    def test_renders_top_stories(self):
        stories = [
            Story(id=1, title="Top story", url="https://example.com", domain="example.com", score=500, descendants=50, by="user"),
            Story(id=2, title="Low story", url="https://other.com", domain="other.com", score=10, descendants=1, by="user"),
        ]
        result = render_digest(stories, date="13/06/2026")
        assert "Top story" in result
        assert "🔥 Top Stories" in result

    def test_renders_category_sections(self):
        stories = [
            Story(id=1, title="Rust release", url="https://github.com/rust", domain="github.com", score=300, descendants=30, by="user"),
        ]
        result = render_digest(stories, date="13/06/2026")
        assert "💻 Programming" in result

    def test_renders_ask_hn(self):
        stories = [
            Story(id=1, title="Ask HN: Something", url=None, domain=None, score=50, descendants=20, by="user"),
        ]
        result = render_digest(stories, date="13/06/2026")
        assert "Ask HN: Something" in result
        # Ask HN should link directly to comments, not article
        assert "[Article]" not in result.split("Ask HN")[1].split("\n")[0]

    def test_daily_stats_line(self):
        stories = [
            Story(id=1, title="A", url="https://example.com", domain="example.com", score=100, descendants=10, by="user"),
        ]
        result = render_digest(stories, date="13/06/2026")
        assert "1 stories" in result
        assert "avg score: 100" in result
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
python -m pytest tests/test_formatter.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'daily_hackernews.formatter'`

- [ ] **Step 5: Write `daily_hackernews/formatter.py`**

```python
"""Format categorized stories into Markdown using Jinja2 templates."""

from __future__ import annotations

import os
from collections import defaultdict

from jinja2 import Environment, FileSystemLoader

from daily_hackernews.categorizer import Category, categorize
from daily_hackernews.fetcher import Story

# Category display order and emoji
CATEGORY_ORDER: list[Category] = [
    Category.PROGRAMMING,
    Category.AI_ML,
    Category.SECURITY,
    Category.DEVOPS,
    Category.BUSINESS,
    Category.DESIGN,
    Category.HARDWARE,
    Category.SCIENCE,
]

CATEGORY_EMOJI: dict[Category, str] = {
    Category.PROGRAMMING: "💻",
    Category.AI_ML: "🤖",
    Category.SECURITY: "🔒",
    Category.DEVOPS: "🛠",
    Category.BUSINESS: "🚀",
    Category.DESIGN: "🎨",
    Category.HARDWARE: "🔧",
    Category.SCIENCE: "🔬",
}

TOP_STORIES_COUNT = 5

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def format_score(score: int) -> str:
    """Format score for display: 1200 → '1.2k', 850 → '850'."""
    if score >= 1000:
        return f"{score / 1000:.1f}k"
    return str(score)


def _get_top_domain(stories: list[Story]) -> str:
    """Return the most common domain among stories."""
    from collections import Counter
    domains = [s.domain for s in stories if s.domain]
    if not domains:
        return "—"
    return Counter(domains).most_common(1)[0][0]


def _get_avg_score(stories: list[Story]) -> str:
    """Return average score formatted for display."""
    if not stories:
        return "0"
    avg = sum(s.score for s in stories) / len(stories)
    return str(int(avg))


class _CategoryView:
    """Wrapper to expose category with emoji for the template."""

    def __init__(self, category: Category):
        self.category = category
        self.value = category.value
        self.emoji = CATEGORY_EMOJI[category]

    def __hash__(self):
        return hash(self.category)

    def __eq__(self, other):
        if isinstance(other, _CategoryView):
            return self.category == other.category
        return NotImplemented


def render_digest(stories: list[Story], date: str) -> str:
    """Render the full digest Markdown from stories and a date string."""
    categorized = categorize(stories)

    # Top stories by score
    sorted_stories = sorted(stories, key=lambda s: s.score, reverse=True)
    top_stories = sorted_stories[:TOP_STORIES_COUNT]

    # Ordered categories that have stories
    categories = [_CategoryView(cat) for cat in CATEGORY_ORDER if cat in categorized]

    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        keep_trailing_newline=True,
    )
    env.filters["fmt_score"] = format_score

    template = env.get_template("digest.md.j2")

    # Build cat_stories with CategoryView keys
    cat_stories = defaultdict(list)
    for cat_view in categories:
        cat_stories[cat_view] = categorized[cat_view.category]

    return template.render(
        date=date,
        stories=stories,
        top_stories=top_stories,
        categories=categories,
        cat_stories=dict(cat_stories),
        avg_score=_get_avg_score(stories),
        top_domain=_get_top_domain(stories),
    )
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pip install jinja2
python -m pytest tests/test_formatter.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add daily_hackernews/formatter.py daily_hackernews/templates/digest.md.j2 tests/test_formatter.py requirements.txt requirements-dev.txt
git commit -m "feat: add Jinja2-based formatter with digest template and tests"
```

---

### Task 4: Publisher

**Files:**
- Create: `daily_hackernews/publisher.py`
- Modify: `requirements.txt` (no changes needed, already has requests)

- [ ] **Step 1: Write `daily_hackernews/publisher.py`**

```python
"""Publish digest as a GitHub Issue."""

from __future__ import annotations

import json
import os

import certifi
import requests

GITHUB_API_URL = "https://api.github.com/repos/blka/daily-hackernews/issues"


def create_issue(title: str, body: str, labels: list[str] | None = None) -> str:
    """Create a GitHub Issue and return its URL.

    Raises on non-201 status.
    """
    token = os.environ.get("ACCESS_TOKEN")
    if not token:
        raise RuntimeError("ACCESS_TOKEN environment variable is not set")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"token {token}",
    }
    payload = {
        "title": title,
        "body": body,
        "labels": labels or ["daily-digest"],
    }

    resp = requests.post(
        GITHUB_API_URL, json=payload, headers=headers, verify=certifi.where(), timeout=30
    )
    if resp.status_code != 201:
        raise RuntimeError(
            f"Failed to create issue: {resp.status_code} {resp.text}"
        )

    data = json.loads(resp.text)
    return data["html_url"]


def lock_issue(issue_url: str) -> bool:
    """Lock a GitHub Issue. Returns True on success."""
    token = os.environ.get("ACCESS_TOKEN")
    if not token:
        raise RuntimeError("ACCESS_TOKEN environment variable is not set")

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {token}",
    }
    payload = {"lock_reason": "too heated"}

    resp = requests.put(
        f"{issue_url}/lock", json=payload, headers=headers, verify=certifi.where(), timeout=30
    )
    return resp.status_code == 204
```

- [ ] **Step 2: Commit**

```bash
git add daily_hackernews/publisher.py
git commit -m "feat: add publisher module for GitHub Issues API"
```

---

### Task 5: Pipeline orchestrator and entry point

**Files:**
- Create: `daily_hackernews/main.py`
- Modify: `main.py` (replace with import from package)

- [ ] **Step 1: Write `daily_hackernews/main.py`**

```python
"""Pipeline orchestrator: fetch → categorize → format → publish."""

from __future__ import annotations

import datetime
import logging
import sys

from daily_hackernews.fetcher import fetch_stories
from daily_hackernews.formatter import render_digest
from daily_hackernews.publisher import create_issue, lock_issue

STORY_COUNT = 25

logger = logging.getLogger(__name__)


def get_date() -> str:
    """Return today's date in DD/MM/YYYY format."""
    now = datetime.datetime.now()
    return f"{str(now.day).zfill(2)}/{str(now.month).zfill(2)}/{now.year}"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    logger.info("Fetching top %d stories from Hacker News...", STORY_COUNT)
    stories = fetch_stories(STORY_COUNT)

    if not stories:
        logger.warning("No stories fetched. Skipping issue creation.")
        return

    logger.info("Fetched %d stories. Rendering digest...", len(stories))
    date = get_date()
    body = render_digest(stories, date=date)

    logger.info("Creating GitHub Issue for %s...", date)
    issue_url = create_issue(f"Daily Hacker News {date}", body)
    logger.info("Issue created: %s", issue_url)

    logger.info("Locking issue...")
    if lock_issue(issue_url):
        logger.info("Issue locked successfully.")
    else:
        logger.warning("Failed to lock issue %s", issue_url)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update root `main.py` to import from package**

Replace the contents of `main.py` with:

```python
from daily_hackernews.main import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS (fetcher + categorizer + formatter).

- [ ] **Step 4: Commit**

```bash
git add daily_hackernews/main.py main.py
git commit -m "feat: add pipeline orchestrator and update entry point"
```

---

### Task 6: Update GitHub Actions workflow

**Files:**
- Modify: `.github/workflows/daily.yml`

- [ ] **Step 1: Update the workflow to use the package**

Replace `.github/workflows/daily.yml` contents with:

```yaml
name: Daily HackerNews

on:
  schedule:
    - cron: '0 9 * * *'
  workflow_dispatch:

jobs:
  get_top_stories:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run digest
        run: python main.py
        env:
          ACCESS_TOKEN: ${{ secrets.SECRET }}
```

Changes from original: `actions/checkout@v3` → `@v4`, removed commented-out sections, no other structural changes.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/daily.yml
git commit -m "chore: update GitHub Actions workflow for package structure"
```

---

### Task 7: Remove old files and clean up

**Files:**
- Delete: `hacker_news.py`
- Delete: `issue.py`
- Delete: `mdutils` from requirements (no longer used)
- Modify: `requirements.txt` (remove mdutils)

- [ ] **Step 1: Remove old source files**

```bash
rm hacker_news.py issue.py
```

- [ ] **Step 2: Update `requirements.txt` to remove mdutils**

```
certifi==2026.5.20
charset-normalizer==3.4.6
idna==3.16
jinja2>=3.1
requests==2.34.2
urllib3==2.7.0
```

- [ ] **Step 3: Remove generated `hacker_news.md` if it exists**

```bash
rm -f hacker_news.md
```

- [ ] **Step 4: Update `.gitignore` to include `hacker_news.md`**

Add to `.gitignore`:

```
hacker_news.md
```

- [ ] **Step 5: Run full test suite to confirm nothing is broken**

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: remove old modules, drop mdutils dependency"
```

---

### Task 8: Integration smoke test

**Files:**
- None (verification only)

- [ ] **Step 1: Run the pipeline locally with a dry-run test**

Add a temporary test to verify the full pipeline works with mocked API calls. Create `tests/test_integration.py`:

```python
"""Integration test — full pipeline with mocked HN API."""

from unittest.mock import patch, MagicMock
from daily_hackernews.fetcher import Story
from daily_hackernews.main import main


def _mock_stories():
    return [
        Story(id=1, title="Rust 2026 Released", url="https://github.com/rust-lang/rust", domain="github.com", score=1200, descendants=342, by="rustacean"),
        Story(id=2, title="New AI Model Breaks Benchmarks", url="https://arxiv.org/abs/2401.1234", domain="arxiv.org", score=800, descendants=150, by="mlresearcher"),
        Story(id=3, title="Critical CVE in OpenSSL", url="https://securitysite.com/cve", domain="securitysite.com", score=500, descendants=89, by="securityperson"),
        Story(id=4, title="Ask HN: Best practices for microservices?", url=None, domain=None, score=120, descendants=45, by="curious"),
        Story(id=5, title="Random interesting thing", url="https://randomsite.org/article", domain="randomsite.org", score=50, descendants=5, by="someone"),
    ]


@patch("daily_hackernews.publisher.lock_issue")
@patch("daily_hackernews.publisher.create_issue")
@patch("daily_hackernews.fetcher.fetch_stories")
def test_full_pipeline(mock_fetch, mock_create, mock_lock):
    mock_fetch.return_value = _mock_stories()
    mock_create.return_value = "https://github.com/blka/daily-hackernews/issues/1"
    mock_lock.return_value = True

    main()

    mock_fetch.assert_called_once_with(25)
    mock_create.assert_called_once()
    # Verify the title format
    call_args = mock_create.call_args
    assert call_args[0][0].startswith("Daily Hacker News")
    # Verify the body contains expected sections
    body = call_args[0][1]
    assert "🔥 Top Stories" in body
    assert "💻 Programming" in body
    assert "🤖 AI/ML" in body
    assert "🔒 Security" in body
    assert "Daily Stats" in body
    assert "1.2k" in body  # formatted score
```

- [ ] **Step 2: Run integration test**

```bash
python -m pytest tests/test_integration.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration test for full pipeline"
```

- [ ] **Step 4: Run complete test suite as final check**

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS.

---

### Task 9: Final cleanup and verification

**Files:**
- Verify all files are in order

- [ ] **Step 1: Verify file structure**

```bash
find daily_hackernews tests -type f | sort
```

Expected output:
```
daily_hackernews/__init__.py
daily_hackernews/categorizer.py
daily_hackernews/fetcher.py
daily_hackernews/formatter.py
daily_hackernews/main.py
daily_hackernews/publisher.py
daily_hackernews/templates/digest.md.j2
tests/conftest.py
tests/test_categorizer.py
tests/test_fetcher.py
tests/test_formatter.py
tests/test_integration.py
```

- [ ] **Step 2: Verify old files are gone**

```bash
ls hacker_news.py issue.py 2>&1
```

Expected: "No such file or directory" for both.

- [ ] **Step 3: Run full test suite one last time**

```bash
python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Final commit if any stray changes**

```bash
git status
# Only commit if there are unstaged changes
```