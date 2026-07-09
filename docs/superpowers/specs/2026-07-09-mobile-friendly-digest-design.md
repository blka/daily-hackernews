# Design Spec: Mobile-Friendly Daily HN Digest Layout

## Date: 2026-07-09
## Status: Approved

## 1. Problem Statement
The current daily HN digest uses Markdown tables to display stories within categories. While these tables look good on desktop, they are not responsive on mobile devices (viewed via mobile browsers or the GitHub app), resulting in horizontal scrolling and a broken layout.

## 2. Proposed Solution
Replace the table-based layout in `digest.md.j2` with a list-based "card" layout. This ensures that the content flows vertically and fits the screen width of any device.

## 3. Detailed Design

### 3.1 Structural Changes
The logic for grouping stories into categories remains unchanged. The change is strictly limited to the Jinja2 template rendering.

### 3.2 New Layout Pattern
For each category, the stories will be rendered as an ordered list. Each item in the list will follow this structure:

1. **Story Title** (as a link to the article)
2. **Metadata Line**: A single line containing:
   - Domain (e.g., `github.com`)
   - Formatted Score (e.g., ⭐ 450)
   - Comments (e.g., [💬 22](link to HN))
3. **Separator**: A horizontal rule (`***`) between items to provide visual breathing room.

### 3.3 Template Modification
The `digest.md.j2` template will be updated.
**Current (Table):**
```markdown
| # | Title | Domain | Score | Comments |
|---|---|---|---|---|
| {{ loop.index }} | [{{ story.title }}]({{ story.url }}) | ... | ... | ... |
```

**Proposed (List):**
```markdown
{{ loop.index }}. **{% if story.url %}[{{ story.title }}]({{ story.url }}){% else %}{{ story.title }}{% endif %}**
   {% if story.domain %}`{{ story.domain }}`{% endif %} · ⭐ {{ story.score | fmt_score }} · [💬 {{ story.descendants }}](https://news.ycombinator.com/item?id={{ story.id }})
   ***
```

## 4. Success Criteria
- No horizontal scrolling on mobile devices.
- All story metadata (domain, score, comments) remains visible.
- Legibility is maintained or improved compared to the desktop table view.
- The "Top Stories" section (which is already a list) remains consistent with the rest of the digest.
