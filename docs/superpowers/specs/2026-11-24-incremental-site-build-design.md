# Incremental Pages site build + authenticated GitHub API

Date: 2026-11-24

## Intent / why

Daily workflow occasionally fails at the "Build site from issues" step with
`403 rate limit exceeded`: `fetch_issues()` calls the GitHub API
unauthenticated (limit 60 req/h per IP, shared across Actions runners) and
fetches the full 520+ issue archive every run. Root cause is the missing
token; the full rebuild makes the failure visible and keeps the archive
re-fetched for no gain. Fix both: authenticate (token) and stop re-fetching
known history (incremental build).

## Goals

- Deploy job never hits the API rate limit.
- Fetch only issues newer than the last built archive.
- Keep page semantics unchanged: one page per date, newest issue number wins.

## Non-goals / anti-goals

- No repo commits from the workflow (`contents: write`, branch hygiene) — rejected.
- No HTML scraping of the live site — rejected (fragile parse, no benefit).
- No changes to digest generation (job `get_top_stories`), categorizer, page/CSS
  layout, or deploy steps (`upload-pages-artifact`, `deploy-pages`).

## Approaches considered

1. **A: Token only, keep full rebuild** — ~10 lines, self-healing. Rejected by
   the user: archive fetch should stop growing even though the token alone
   solves the rate limit.
2. **B: Incremental with `actions/cache` on the `site/` dir** — old pages,
   index and `manifest.json` live in a workflow cache; each run renders only
   new pages. **Picked.**
3. Commit `site/` to the repo — rejected: more moving parts than cache for the
   same result.
4. Scrape old pages from the live site — rejected: Pages deploys are atomic, so
   old page HTML would have to be re-downloaded anyway (more traffic than the
   6 API calls it replaces).

## Design

### site.py

- `fetch_issues()` gains an optional `token` parameter; when set, sends
  `Authorization: Bearer <token>` header. Retry on 403/429 with backoff
  (respect `X-RateLimit-Reset` when present; bounded retries, then fail loudly).
- New incremental mode in `main()`/`build_site()`:
  - Read `manifest.json` from the output dir. Missing/corrupt → full mode.
  - Manifest entry per built page: `{page_path, number, title, date}` plus the
    newest issue number covered per date (implicit: entry's number is the winner).
  - Fetch issues newest-first as today, with early stop: when a fetched issue's
    number ≤ smallest manifest number, stop paging.
  - New batch: within-batch dedup by date (highest number wins — existing rule);
    a date already in the manifest → new issue is newer, regenerate that page
    and overwrite the manifest entry.
  - Render only new/overridden pages; rebuild `index.html` from all manifest
    entries (archive section) plus the latest digest.
  - Write updated `manifest.json` into the output dir.
- Full mode is the current behavior, unchanged, and also serves as fallback.

### daily.yml (deploy job)

- Pass `GITHUB_TOKEN: ${{ github.token }}` env to the build step.
- `actions/cache` step: restore/save path `site`, key on the workflow name
  (restore-key fallback to the newest cache). Cache miss → full rebuild
  fallback, then the cache is refreshed with the full site.
- Cache is saved after a successful build; a failed run leaves the previous
  cache intact, so the next run just rebuilds that one day if it missed.

## Constraints

- Public site URL and layout stay identical.
- `manifest.json` lands in the deployed Pages artifact (public, harmless —
  it is derived from public issues).
- Tests must cover: token header, early stop, manifest load/save, same-date
  override from manifest, fallback to full mode, retry on 403.

## Left to the builder

- Exact cache key scheme and retry timings.
- Manifest JSON shape details (single top-level object, list + min number).
- Test placement in the existing pytest suite.
