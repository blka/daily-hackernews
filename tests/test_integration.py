"""Integration test — full pipeline with mocked HN API."""

from unittest.mock import patch
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


@patch("daily_hackernews.main.lock_issue")
@patch("daily_hackernews.main.create_issue")
@patch("daily_hackernews.main.fetch_stories")
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