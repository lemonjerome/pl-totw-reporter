# Premier League Website — Navigation Guide

Navigation patterns for scraping the PL website using Playwright.

## Base URL & Structure

- **Base**: `https://www.premierleague.com`
- **Matches**: `/matches`
- **Clubs**: `/clubs`
- **Players**: `/players`
- **News**: `/news`
- **Individual match**: `/match/{match_id}` — match_id is the PL internal ID
- **Season context**: `window.ACTIVE_PL_MATCHWEEK_ID` and `window.ACTIVE_PL_SEASON_ID` are set in JS

## Important: The PL API

The PL website loads data from a REST API. We can query this directly (much more reliable than scraping rendered HTML):

- **PL API base**: `https://api.premierleague.com`
- **Fixtures for a matchweek**: `https://api.premierleague.com/fixtures?gameweek={N}&compSeasons.label=2024%2F25`
- **Match summary**: `https://api.premierleague.com/match/{match_id}`
- **Match stats**: `https://api.premierleague.com/match/{match_id}/stats`

However, the PL API does not provide commentary or match reports — those require web scraping.

## Playwright Navigation Patterns

### Initial Setup

```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()
    await page.set_extra_http_headers({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    })
```

### Handling Cookie Consent

The PL website shows a cookie banner. Dismiss it first:
```python
await page.goto("https://www.premierleague.com/matches")
# Wait for and dismiss cookie banner
try:
    await page.click(".js-accept-all-close", timeout=5000)
except:
    pass  # Banner may not appear every time
await page.wait_for_load_state("networkidle")
```

### Getting Match Reports

Match reports are published in the News section, linked from match pages.

1. Navigate to the match page: `https://www.premierleague.com/match/{match_id}`
2. Wait for page to load
3. Look for a "Match Report" link or button
4. Click and extract article text from `article.news-article__content` or similar

Alternative: Search the news page for match report:
```
https://www.premierleague.com/news?category=match-reports
```

### Getting Match Commentary

1. Navigate to: `https://www.premierleague.com/match/{match_id}`
2. Wait for page to load
3. Click the "Commentary" tab (look for `[data-panel-id="commentary"]` or tab button with text "Commentary")
4. Wait for commentary content to load
5. Extract: `document.querySelectorAll('.comment-body')` or similar selectors

Commentary is typically loaded dynamically — wait for it:
```python
await page.click('[data-label="Commentary"]')
await page.wait_for_selector('.commentary-item', timeout=10000)
comments = await page.query_selector_all('.commentary-item')
```

### Getting Clubs List

1. Navigate to: `https://www.premierleague.com/clubs`
2. Each club card has name, badge, and link to club page
3. Club pages link to club's official website
4. Extract: club name + official website URL from club page

```python
await page.goto("https://www.premierleague.com/clubs")
await page.wait_for_selector('.club-card', timeout=10000)
clubs = await page.query_selector_all('.club-card')
```

### Getting Player Images

Player images are **not reliably available on the PL website itself**. Use this priority order:

1. **API-Football CDN** (easiest): `https://media.api-sports.io/football/players/{player_id}.png` — use player_id from fixtures/players API response
2. **PL Resources CDN**: `https://resources.premierleague.pulselive.com/photo-resources/` — requires knowing the PL player ID
3. **Club website**: Navigate to the club's official website → Squad/Team → find player profile → screenshot or download player image
   - This requires navigating to each club's website (different for every club)
   - Selector patterns vary significantly per club
   - Use as last resort

**Recommended**: Use API-Football player photos (`media.api-sports.io/football/players/{id}.png`) for the slides. These are reliable and do not require additional scraping.

### Matchweek Fixtures Page

To get the current matchweek's fixture list with PL match IDs:

```python
await page.goto("https://www.premierleague.com/matches")
await page.wait_for_load_state("networkidle")
# The matchweek number and match IDs are embedded in the rendered HTML
match_elements = await page.query_selector_all('[data-fixtureId]')
```

Or use the PL API directly:
```
https://api.premierleague.com/fixtures?gameweeks={N}
```

## Key CSS Selectors

These selectors are based on the PL website's structure (may change with site updates):

| Element | Selector |
|---------|----------|
| Cookie consent dismiss | `.js-accept-all-close` |
| Match card | `.match-fixture` |
| Fixture date | `.match-fixture__date` |
| Home team name | `.match-fixture__team--home .match-fixture__team-name` |
| Away team name | `.match-fixture__team--away .match-fixture__team-name` |
| Score | `.match-fixture__score` |
| Commentary tab | `[data-panel-id="commentary"]` or `button[data-label="Commentary"]` |
| Commentary items | `.commentary-item, .comment-body` |
| News article body | `.article__inner, .news-article__content` |
| Club badge | `.badge-image, img[alt*="badge"]` |

## Reliability Tips

1. **Always use `networkidle`** wait state after navigation — PL site is SPA with heavy JS
2. **Retry on timeout**: The PL site can be slow; retry up to 3 times
3. **Screenshot on failure**: Take a screenshot if a selector is not found (debug tool)
4. **Rate limit yourself**: Add a `asyncio.sleep(1-2)` between requests to avoid getting blocked
5. **Fallback**: If scraping fails, note "Match report not available" in the report and proceed

## Data Storage

Save scraped content to:
```
data/2025-26/matchweek-{N}/
  reports/
    {fixture_id}_report.txt    # Match report text
    {fixture_id}_commentary.txt  # Commentary text
```
