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
    """Extract the domain from a URL, stripping www. prefix."""
    m = re.search(r"https?://(?:www\.)?([A-Za-z_0-9.-]+)", url)
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