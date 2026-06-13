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