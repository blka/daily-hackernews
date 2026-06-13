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
    "anthropic.com": Category.AI_ML,
    "nature.com": Category.SCIENCE,
    "sciencedirect.com": Category.SCIENCE,
}

# Keyword → Category (case-insensitive match in title, first match wins)
# Security keywords listed first so "malware" beats "developer" etc.
KEYWORD_MAP: list[tuple[str, Category]] = [
    # Security (high priority — beats broader keywords like "developer")
    ("vulnerability", Category.SECURITY),
    ("CVE", Category.SECURITY),
    ("exploit", Category.SECURITY),
    ("breach", Category.SECURITY),
    ("hack", Category.SECURITY),
    ("security", Category.SECURITY),
    ("ransomware", Category.SECURITY),
    ("malware", Category.SECURITY),
    # AI/ML
    ("AI", Category.AI_ML),
    ("LLM", Category.AI_ML),
    ("GPT", Category.AI_ML),
    ("neural", Category.AI_ML),
    ("machine learning", Category.AI_ML),
    ("transformer", Category.AI_ML),
    ("deep learning", Category.AI_ML),
    ("model", Category.AI_ML),
    ("chatbot", Category.AI_ML),
    # Programming
    ("python", Category.PROGRAMMING),
    ("rust", Category.PROGRAMMING),
    ("javascript", Category.PROGRAMMING),
    ("typescript", Category.PROGRAMMING),
    ("compiler", Category.PROGRAMMING),
    ("language", Category.PROGRAMMING),
    ("framework", Category.PROGRAMMING),
    ("library", Category.PROGRAMMING),
    ("programming", Category.PROGRAMMING),
    ("code", Category.PROGRAMMING),
    ("developer", Category.PROGRAMMING),
    # DevOps/Infra
    ("kubernetes", Category.DEVOPS),
    ("docker", Category.DEVOPS),
    ("container", Category.DEVOPS),
    ("cloud", Category.DEVOPS),
    ("terraform", Category.DEVOPS),
    ("CI/CD", Category.DEVOPS),
    ("deploy", Category.DEVOPS),
    ("infrastructure", Category.DEVOPS),
    ("serverless", Category.DEVOPS),
    # Business/Startups
    ("startup", Category.BUSINESS),
    ("VC", Category.BUSINESS),
    ("funding", Category.BUSINESS),
    ("IPO", Category.BUSINESS),
    ("revenue", Category.BUSINESS),
    ("founder", Category.BUSINESS),
    ("SaaS", Category.BUSINESS),
    ("enterprise", Category.BUSINESS),
    # Design/Product
    ("UX", Category.DESIGN),
    ("UI", Category.DESIGN),
    ("design", Category.DESIGN),
    ("product", Category.DESIGN),
    ("interface", Category.DESIGN),
    ("usability", Category.DESIGN),
    ("accessibility", Category.DESIGN),
    # Hardware/IoT
    ("hardware", Category.HARDWARE),
    ("chip", Category.HARDWARE),
    ("CPU", Category.HARDWARE),
    ("GPU", Category.HARDWARE),
    ("embedded", Category.HARDWARE),
    ("IoT", Category.HARDWARE),
    ("Raspberry", Category.HARDWARE),
    ("FPGA", Category.HARDWARE),
    ("semiconductor", Category.HARDWARE),
    # Science/Other
    ("quantum", Category.SCIENCE),
    ("physics", Category.SCIENCE),
    ("biology", Category.SCIENCE),
    ("research", Category.SCIENCE),
    ("science", Category.SCIENCE),
    ("space", Category.SCIENCE),
    ("climate", Category.SCIENCE),
]


def categorize_story(story: Story) -> Category:
    """Assign a category to a single story. Domain match takes priority over keyword."""
    # 1. Domain match
    if story.domain and story.domain in DOMAIN_MAP:
        return DOMAIN_MAP[story.domain]

    # 2. Keyword match (case-insensitive, first match wins)
    title_lower = story.title.lower()
    for keyword, category in KEYWORD_MAP:
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