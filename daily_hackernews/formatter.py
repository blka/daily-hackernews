"""Format categorized stories into Markdown using Jinja2 templates."""

from __future__ import annotations

import os
from collections import Counter, defaultdict

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