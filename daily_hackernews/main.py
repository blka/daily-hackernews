"""Pipeline orchestrator: fetch → categorize → format → publish."""

from __future__ import annotations

import datetime
import logging

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