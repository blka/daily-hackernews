# Daily Hacker News

Top 25 stories from Hacker News, posted as an issue every day.

## Read it

- **Website:** https://blka.github.io/daily-hackernews/
- **Issues:** [issues labeled daily-digest](https://github.com/blka/daily-hackernews/issues?q=label%3Adaily-digest%20is%3Aopen) — subscribe by watching this repo

## How does it work

1. A scheduled GitHub Action (09:00 UTC) fetches the top 25 stories from hackernews and opens a locked issue labeled `daily-digest`
2. Each issue marks the top 5 stories by score with 🔥; stories without a URL link to the HN item page
3. A second job converts every digest issue to a static site and deploys it to GitHub Pages