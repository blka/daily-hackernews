# Daily HackerNews Digest — Design Spec

**Date:** 2026-06-13
**Status:** Approved

## Goal

Rewrite the Daily HackerNews project from a minimal script that posts raw links as GitHub Issues into a well-structured daily digest with categories, top stories highlights, and a daily summary — delivered as nicely formatted GitHub Issues. No AI, no external APIs beyond HN Firebase. No infrastructure changes.

## Current State

- 3 Python files (~130 LOC): `main.py`, `hacker_news.py`, `issue.py`
- GitHub Actions cron at 9:00 UTC daily
- Output: flat numbered list of 25 stories with title, domain, comments link
- Delivered as GitHub Issues; users subscribe by watching the repo

## Requirements

1. Categorize stories into ~8 categories using domain + keyword heuristics
2. Highlight top 5 stories by score at the top
3. Include a daily stats summary (total stories, avg score, top domain)
4. Better Markdown formatting with emoji category headers
5. Handle Ask HN posts (no URL) with direct HN links
6. Stay on GitHub Actions + GitHub Issues — no new delivery infrastructure
7. English language for all output
8. No AI/LLM — pure heuristics

## Architecture

```
daily_hackernews/
├── __init__.py
├── fetcher.py       # HN API client → list[Story]
├── categorizer.py   # keyword/domain mapping → dict[Category, list[Story]]
├── formatter.py     # Jinja2 templates → Markdown string
├── publisher.py     # GitHub Issues API → create + lock issue
└── main.py          # orchestrator: fetch → categorize → format → publish
```

Each module has a single responsibility. `main.py` orchestrates the pipeline.

## Fetcher

- Query HN Firebase API for top 25 stories (as today)
- Fetch each item's details
- Return `list[Story]` where `Story` is a dataclass:

```python
@dataclass
class Story:
    id: int
    title: str
    url: str | None  # None for Ask HN
    domain: str | None
    score: int
    descendants: int  # comment count
    by: str
```

- Handle missing fields: Ask HN has no URL, some items lack `score` or `descendants`

## Categorizer

- Input: `list[Story]`
- Output: `dict[Category, list[Story]]`
- Category enum with ~8 values: Programming, AI/ML, Security, DevOps/Infra, Business/Startups, Design/Product, Hardware/IoT, Science/Other
- Matching rules (first match wins):
  1. Domain match (e.g., `github.com` → Programming, `arxiv.org` → AI/ML)
  2. Keyword match in title (case-insensitive)
  3. No match → Other (merged into Science/Other)
- Domain and keyword mappings are defined as module-level constants for easy editing

### Category Mapping

| Category | Domain matches | Keyword matches |
|---|---|---|
| Programming | github.com, gitlab.com, stackoverflow.com, docs.python.org, docs.rs | python, rust, go lang, javascript, typescript, compiler, language, framework, library, programming, code, developer |
| AI/ML | arxiv.org, openai.com, deepmind.com, huggingface.co | AI, LLM, GPT, neural, machine learning, transformer, deep learning, model, chatbot |
| Security | krebsonsecurity.com, schneier.com, thehackernews.com | vulnerability, CVE, exploit, breach, hack, security, ransomware, malware |
| DevOps/Infra | docker.com, kubernetes.io, hashicorp.com | kubernetes, docker, container, cloud, terraform, CI/CD, deploy, infrastructure, serverless |
| Business/Startups | techcrunch.com, ycombinator.com, crunchbase.com | startup, VC, funding, IPO, revenue, founder, SaaS, enterprise |
| Design/Product | figma.com, medium.com, uxdesign.cc | UX, UI, design, product, interface, usability, accessibility |
| Hardware/IoT | — | hardware, chip, CPU, GPU, embedded, IoT, Raspberry, FPGA, semiconductor |
| Science/Other | nature.com, sciencedirect.com, arxiv.org (fallback) | quantum, physics, biology, research, science, space, climate |

Note: `arxiv.org` matches AI/ML first by domain; Science catches arxiv papers that didn't match AI/ML keywords.

## Formatter

- Input: `dict[Category, list[Story]]`, `list[Story]` (top stories), date string
- Output: Markdown string (GitHub-flavored)
- Uses Jinja2 template for structure

### Template Structure

```markdown
# Daily Hacker News — DD/MM/YYYY

> **Daily Stats:** 25 stories · avg score: 342 · top domain: github.com

## 🔥 Top Stories

1. **Story Title** `domain` — ⭐ 1.2k · 💬 342
   [Article](url) · [Comments](hn_comments_url)

---

## 💻 Programming
| # | Title | Domain | Score | Comments |
|---|---|---|---|---|
| 6 | [Title](url) | domain | 450 | [💬 89](hn_url) |

---

## 🤖 AI/ML
...

## 🔒 Security
...

## 🛠 DevOps/Infra
...

## 🚀 Business/Startups
...

## 🎨 Design/Product
...

## 🔧 Hardware/IoT
...

## 🔬 Science/Other
...
```

- Top Stories section: top 5 by score, with formatted links
- Category sections: table format with story details
- Ask HN posts: direct HN link instead of article URL
- Score formatting: `1.2k` for scores ≥ 1000, else plain number
- Category emoji headers for visual distinction

## Publisher

- Input: title string, body Markdown string
- Create GitHub Issue via REST API (as today)
- Add label `daily-digest`
- Lock issue after creation (as today)
- Error handling: raise on non-201 status

## GitHub Actions

No changes to workflow structure. Only:
- Add `jinja2` to `requirements.txt`
- Python version remains 3.10
- Single new dependency: jinja2

## Dependencies

```
requests>=2.28
jinja2>=3.1
certifi>=2023.7.22
```

`mdutils` is removed — replaced by Jinja2 templates.

## Error Handling

- Network errors: raise with descriptive message (Actions will show in logs)
- Missing story fields: default to sensible values (score=0, descendants=0, url=None)
- GitHub API errors: raise on non-201 for issue creation
- No stories fetched: skip issue creation, log warning

## Testing

- Unit tests for categorizer (keyword/domain matching, edge cases)
- Unit tests for formatter (template rendering, Ask HN handling, score formatting)
- Integration test with mocked HN API responses
- No tests for publisher (thin GitHub API wrapper)

## Out of Scope

- AI/LLM-generated summaries
- Algolia HN Search API integration
- Email delivery (staying with GitHub Issues notifications)
- Web UI or dashboard
- Comment analysis or sentiment
- Historical data or trending analysis