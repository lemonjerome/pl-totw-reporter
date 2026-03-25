"""
PL Website Scraper for the EPL TOTW Builder.

Scrapes the Premier League website for:
- Match reports (linked from individual PL match pages)
- Match commentaries (Commentary tab on PL match pages)

Strategy:
1. Scrape the PL Results page with Playwright to find match page links
2. Navigate to each match page: https://www.premierleague.com/match/{pl_id}
3. Extract match report text and match commentary

IMPORTANT: This scraper works best for the CURRENT season's matchweeks,
where the Results page shows links to recent match pages. For historical
matchweeks (previous seasons), the Results page may not list those games.
In that case, scraping is skipped gracefully and reports are left empty.

All results are cached in:
    data/2025-26/matchweek-{N}/reports/{fixture_id}_report.txt
    data/2025-26/matchweek-{N}/commentaries/{fixture_id}_commentary.txt

CLI:
    python scripts/pl_scraper.py all 30
    python scripts/pl_scraper.py match-reports 30
    python scripts/pl_scraper.py commentary 30
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import (
    cache_exists,
    load_json_cache,
    load_text_cache,
    matchweek_commentaries_dir,
    matchweek_data_dir,
    matchweek_reports_dir,
    save_json_cache,
    save_text_cache,
)

PL_BASE = "https://www.premierleague.com"
PAGE_DELAY = 2.5    # seconds between page navigations
RESULTS_PAGES = [
    f"{PL_BASE}/results",
    f"{PL_BASE}/results?co=1",
    f"{PL_BASE}/matches?type=results",
]


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def load_fixtures(matchweek: int) -> list[dict]:
    path = matchweek_data_dir(matchweek) / "fixtures.json"
    data = load_json_cache(path)
    if not data:
        raise FileNotFoundError(
            f"No fixtures cache for matchweek {matchweek}. "
            f"Run: python scripts/api_football.py fetch-round {matchweek}"
        )
    return [f for f in data if f["fixture"]["status"]["short"] in ("FT", "AET", "PEN")]


def apifootball_id(f: dict) -> int:
    return f["fixture"]["id"]


def team_names(f: dict) -> tuple[str, str]:
    return f["teams"]["home"]["name"], f["teams"]["away"]["name"]


# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------

async def _new_page(browser):
    page = await browser.new_page()
    await page.set_extra_http_headers({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-GB,en;q=0.9",
    })
    return page


async def _goto(page, url: str, timeout: int = 30000) -> bool:
    for attempt in range(3):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            return True
        except Exception as e:
            if attempt == 2:
                print(f"    ✗ Failed ({type(e).__name__}): {url[:80]}")
                return False
            await page.wait_for_timeout(2000)
    return False


async def _dismiss_cookies(page) -> None:
    for sel in [
        ".js-accept-all-close",
        "#onetrust-accept-btn-handler",
        "button:has-text('Accept All Cookies')",
        "button:has-text('Accept all')",
    ]:
        try:
            await page.click(sel, timeout=3000)
            await page.wait_for_timeout(500)
            return
        except Exception:
            continue


# ---------------------------------------------------------------------------
# Step 1: Discover PL match page IDs from the Results page
# ---------------------------------------------------------------------------

async def discover_pl_fixture_ids(page, matchweek: int, fixtures: list[dict]) -> dict[int, int]:
    """
    Scrape the PL Results page to find match page URLs and extract internal fixture IDs.
    Returns {api_football_id: pl_internal_id}.
    Results are cached in data/2025-26/matchweek-{N}/pl_fixture_ids.json.
    """
    cache_path = matchweek_data_dir(matchweek) / "pl_fixture_ids.json"
    cached = load_json_cache(cache_path)
    if cached and len(cached) > 0:
        result = {int(k): int(v) for k, v in cached.items()}
        print(f"  PL fixture IDs: {len(result)} loaded from cache")
        return result

    print(f"  Discovering PL match page IDs from Results page...")

    # Build home-team lookup (first significant word of home team name)
    home_lookup: dict[str, int] = {}
    for f in fixtures:
        home = f["teams"]["home"]["name"].lower()
        home_lookup[home] = apifootball_id(f)
        # Index by first word (e.g. "Arsenal" from "Arsenal")
        first_word = home.split()[0]
        home_lookup[first_word] = apifootball_id(f)
        # Also index by common short name (e.g. "man" for "Manchester City")
        if len(home.split()) > 1:
            home_lookup[" ".join(home.split()[:2])] = apifootball_id(f)

    id_map: dict[int, int] = {}

    for results_url in RESULTS_PAGES:
        ok = await _goto(page, results_url)
        if not ok:
            continue

        await _dismiss_cookies(page)
        await page.wait_for_timeout(4000)

        # Look for scrollable fixture list and try to navigate to older gameweeks
        # The PL results page often has a gameweek selector
        await _try_navigate_to_gameweek(page, matchweek)
        await page.wait_for_timeout(2000)

        links = await _extract_match_links(page)
        id_map.update(_match_links_to_fixtures(links, home_lookup))

        if len(id_map) >= 3:  # Got enough matches
            break

    if id_map:
        save_json_cache(cache_path, {str(k): v for k, v in id_map.items()})
        print(f"  Found {len(id_map)}/{len(fixtures)} PL match page IDs")
    else:
        print(f"  ✗ Could not find PL match IDs — likely a previous-season matchweek")
        print(f"    (Scraper works best for the current active season)")

    return id_map


async def _try_navigate_to_gameweek(page, matchweek: int) -> None:
    """Try to click to the target matchweek on the results page."""
    # Some PL page versions have a GW selector; try clicking "previous" until we find GW N
    # This is a best-effort attempt
    for _ in range(5):
        try:
            gw_text = await page.evaluate("""
                () => {
                    const el = document.querySelector('[class*="gameweek"], [class*="round"]');
                    return el ? el.innerText : '';
                }
            """)
            if gw_text and str(matchweek) in gw_text:
                return

            # Try clicking a "previous" / "<" button
            for sel in ["button[aria-label='Previous']", ".prev-btn", "[class*='prev']"]:
                try:
                    await page.click(sel, timeout=1500)
                    await page.wait_for_timeout(800)
                    break
                except Exception:
                    continue
        except Exception:
            break


async def _extract_match_links(page) -> list[dict]:
    """Extract all /match/ links from the current page."""
    try:
        return await page.evaluate("""
            () => Array.from(document.querySelectorAll('a'))
                .filter(a => a.href.includes('/match/') && a.href.includes('premierleague.com'))
                .map(a => {
                    const m = a.href.match(/\\/match\\/(\\d+)/);
                    return {
                        pl_id: m ? parseInt(m[1]) : null,
                        href: a.href,
                        text: (a.innerText || '').toLowerCase().trim()
                    };
                })
                .filter(l => l.pl_id !== null)
        """)
    except Exception:
        return []


def _match_links_to_fixtures(links: list[dict], home_lookup: dict[str, int]) -> dict[int, int]:
    """Map PL match links to API-Football fixture IDs by team name matching."""
    id_map: dict[int, int] = {}
    for link in links:
        pl_id = link.get("pl_id")
        text = link.get("text", "")
        if not pl_id:
            continue
        for home_name, api_fid in home_lookup.items():
            if home_name in text and api_fid not in id_map:
                id_map[api_fid] = pl_id
                break
    return id_map


# ---------------------------------------------------------------------------
# Step 2: Scrape a single match page
# ---------------------------------------------------------------------------

async def _scrape_match_page(page, pl_id: int, home: str, away: str) -> tuple[str, str]:
    """
    Navigate to a PL match page and extract report + commentary.
    Returns (report_text, commentary_text).
    """
    url = f"{PL_BASE}/match/{pl_id}"
    ok = await _goto(page, url)
    if not ok:
        return "", ""

    await _dismiss_cookies(page)
    await page.wait_for_timeout(3000)

    # Verify we landed on the right match (check team names in page content)
    page_text = await page.evaluate("() => document.body.innerText.toLowerCase()")
    home_word = home.split()[0].lower()
    away_word = away.split()[0].lower()
    if home_word not in page_text and away_word not in page_text:
        print(f"    ⚠ Wrong match page (expected {home} vs {away})")
        return "", ""

    report = await _extract_match_report(page, home, away)
    commentary = await _extract_commentary(page)
    return report, commentary


async def _extract_match_report(page, home: str, away: str) -> str:
    """Find and fetch the match report article from the match page."""
    home_words = {w.lower() for w in home.split() if len(w) > 3}
    away_words = {w.lower() for w in away.split() if len(w) > 3}
    all_words = home_words | away_words

    # Collect links that look like match reports
    links = await page.evaluate("""
        () => Array.from(document.querySelectorAll('a'))
            .filter(a =>
                a.href.includes('/news/') &&
                a.href.includes('premierleague.com') &&
                (
                    a.href.toLowerCase().includes('match-report') ||
                    (a.innerText || '').toLowerCase().includes('match report') ||
                    (a.getAttribute('aria-label') || '').toLowerCase().includes('match report')
                )
            )
            .map(a => ({
                href: a.href,
                text: ((a.innerText || '') + ' ' + (a.getAttribute('aria-label') || '')).toLowerCase()
            }))
    """)

    if not links:
        return ""

    # Score links by team name mentions
    def score(link: dict) -> int:
        t = link.get("text", "") + " " + link.get("href", "").lower()
        return sum(1 for w in all_words if w in t)

    sorted_links = sorted(links, key=score, reverse=True)

    for link in sorted_links[:3]:
        href = link.get("href", "")
        if not href:
            continue
        try:
            ok = await _goto(page, href)
            if not ok:
                continue
            await page.wait_for_timeout(1500)

            text = await _extract_article_text(page)

            # Validate: article should mention at least one team
            text_lower = text.lower()
            if len(text) > 300 and any(w in text_lower for w in all_words):
                return text

            # Navigate back if this was wrong
            await page.go_back()
            await page.wait_for_timeout(1000)
        except Exception:
            continue

    return ""


async def _extract_article_text(page) -> str:
    """Extract the main article body text from the current page."""
    for sel in [
        "article",
        ".article__body",
        ".article__inner",
        ".news-article__content",
        "[class*='articleBody']",
        "main",
    ]:
        try:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if len(text) > 300:
                    lines = [l.strip() for l in text.splitlines() if l.strip() and len(l.strip()) > 5]
                    return "\n".join(lines)
        except Exception:
            continue
    return ""


async def _extract_commentary(page) -> str:
    """Click the Commentary tab and extract commentary events."""
    # Click the Commentary tab
    clicked = False
    for sel in [
        "li[data-panel-id='commentary']",
        "button[data-label='Commentary']",
        "a[data-label='Commentary']",
        "[aria-label='Commentary']",
        "li:has-text('Commentary')",
        "button:has-text('Commentary')",
    ]:
        try:
            await page.click(sel, timeout=4000)
            clicked = True
            break
        except Exception:
            continue

    if not clicked:
        try:
            await page.get_by_text("Commentary").first.click(timeout=3000)
            clicked = True
        except Exception:
            pass

    if clicked:
        await page.wait_for_timeout(3000)

    # Try multiple selectors to extract commentary events
    lines: list[str] = []

    for sel in [
        ".commentary-item",
        ".comment-body",
        "[class*='Commentary']",
        "[class*='commentary']",
        "[data-event-type]",
    ]:
        try:
            items = await page.query_selector_all(sel)
            if len(items) >= 3:
                for item in items:
                    t = (await item.inner_text()).strip()
                    if t and len(t) > 5:
                        lines.append(t)
                if lines:
                    break
        except Exception:
            continue

    # Fallback: look for timeline/events via JS
    if not lines:
        try:
            raw = await page.evaluate("""
                () => {
                    const candidates = [
                        '[class*="timeline"]', '[class*="feed"]',
                        '[class*="event"]',    '[class*="incident"]',
                    ];
                    for (const sel of candidates) {
                        const els = document.querySelectorAll(sel);
                        if (els.length >= 5) {
                            return Array.from(els)
                                .map(e => e.innerText.trim())
                                .filter(t => t.length > 5);
                        }
                    }
                    return [];
                }
            """)
            if raw:
                lines = raw
        except Exception:
            pass

    # Deduplicate
    seen: set[str] = set()
    unique: list[str] = []
    for line in lines:
        if line not in seen:
            seen.add(line)
            unique.append(line)

    return "\n".join(unique)


# ---------------------------------------------------------------------------
# Main orchestrators
# ---------------------------------------------------------------------------

async def scrape_all(matchweek: int) -> None:
    """Single browser session — scrape reports + commentary for all fixtures."""
    from playwright.async_api import async_playwright

    fixtures = load_fixtures(matchweek)
    print(f"\nScraping {len(fixtures)} fixtures for matchweek {matchweek}...")

    # Check what still needs scraping
    to_scrape: list[dict] = []
    for f in fixtures:
        fid = apifootball_id(f)
        home, away = team_names(f)
        r_cached = cache_exists(matchweek_reports_dir(matchweek) / f"{fid}_report.txt")
        c_cached = cache_exists(matchweek_commentaries_dir(matchweek) / f"{fid}_commentary.txt")
        if r_cached and c_cached:
            print(f"  ✓ All cached: {home} vs {away}")
        else:
            to_scrape.append(f)

    if not to_scrape:
        print("  All data already cached.")
        return

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await _new_page(browser)

        pl_ids = await discover_pl_fixture_ids(page, matchweek, fixtures)

        if not pl_ids:
            print("\n  No PL match page IDs found — skipping web scraping.")
            print("  Note: The PL website scraper works best for the current active season.")
            print("  Player stats from API-Football are still available for TOTW generation.")
            await browser.close()
            return

        for f in to_scrape:
            fid = apifootball_id(f)
            home, away = team_names(f)
            pl_id = pl_ids.get(fid)

            if not pl_id:
                print(f"  ✗ No match page ID: {home} vs {away}")
                continue

            print(f"  Scraping: {home} vs {away}...")
            report, commentary = await _scrape_match_page(page, pl_id, home, away)

            r_path = matchweek_reports_dir(matchweek) / f"{fid}_report.txt"
            c_path = matchweek_commentaries_dir(matchweek) / f"{fid}_commentary.txt"

            if report and not cache_exists(r_path):
                save_text_cache(r_path, report)
                print(f"    Report:     {len(report)} chars")
            elif not report:
                print(f"    Report:     not found")

            if commentary and not cache_exists(c_path):
                save_text_cache(c_path, commentary)
                print(f"    Commentary: {len(commentary.splitlines())} events")
            elif not commentary:
                print(f"    Commentary: not found")

            await asyncio.sleep(PAGE_DELAY)

        await browser.close()

    print(f"\nDone. Output in data/2025-26/matchweek-{matchweek}/")


async def scrape_match_reports(matchweek: int, fixtures: list[dict]) -> dict[int, str]:
    """Scrape match reports only. Returns {fixture_id: text}."""
    from playwright.async_api import async_playwright

    results: dict[int, str] = {}
    to_scrape: list[dict] = []

    for f in fixtures:
        fid = apifootball_id(f)
        path = matchweek_reports_dir(matchweek) / f"{fid}_report.txt"
        if cache_exists(path):
            home, away = team_names(f)
            print(f"  ✓ Report cached: {home} vs {away}")
            results[fid] = load_text_cache(path) or ""
        else:
            to_scrape.append(f)

    if not to_scrape:
        return results

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await _new_page(browser)
        pl_ids = await discover_pl_fixture_ids(page, matchweek, fixtures)

        for f in to_scrape:
            fid = apifootball_id(f)
            home, away = team_names(f)
            pl_id = pl_ids.get(fid)

            if not pl_id:
                print(f"  ✗ No match page: {home} vs {away}")
                continue

            print(f"  Fetching report: {home} vs {away}...")
            report, _ = await _scrape_match_page(page, pl_id, home, away)

            if report:
                path = matchweek_reports_dir(matchweek) / f"{fid}_report.txt"
                save_text_cache(path, report)
                results[fid] = report
                print(f"    Saved ({len(report)} chars)")
            else:
                print(f"    Not found")

            await asyncio.sleep(PAGE_DELAY)

        await browser.close()
    return results


async def scrape_commentary(matchweek: int, fixtures: list[dict]) -> dict[int, str]:
    """Scrape match commentary only. Returns {fixture_id: text}."""
    from playwright.async_api import async_playwright

    results: dict[int, str] = {}
    to_scrape: list[dict] = []

    for f in fixtures:
        fid = apifootball_id(f)
        path = matchweek_commentaries_dir(matchweek) / f"{fid}_commentary.txt"
        if cache_exists(path):
            home, away = team_names(f)
            print(f"  ✓ Commentary cached: {home} vs {away}")
            results[fid] = load_text_cache(path) or ""
        else:
            to_scrape.append(f)

    if not to_scrape:
        return results

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await _new_page(browser)
        pl_ids = await discover_pl_fixture_ids(page, matchweek, fixtures)

        for f in to_scrape:
            fid = apifootball_id(f)
            home, away = team_names(f)
            pl_id = pl_ids.get(fid)

            if not pl_id:
                print(f"  ✗ No match page: {home} vs {away}")
                continue

            print(f"  Fetching commentary: {home} vs {away}...")
            _, commentary = await _scrape_match_page(page, pl_id, home, away)

            if commentary:
                path = matchweek_commentaries_dir(matchweek) / f"{fid}_commentary.txt"
                save_text_cache(path, commentary)
                results[fid] = commentary
                print(f"    Saved ({len(commentary.splitlines())} events)")
            else:
                print(f"    Not found")

            await asyncio.sleep(PAGE_DELAY)

        await browser.close()
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/pl_scraper.py <command> <matchweek>")
        print("Commands: all | match-reports | commentary")
        print()
        print("Note: Works best for the current active season's matchweeks.")
        sys.exit(1)

    command = sys.argv[1]
    matchweek = int(sys.argv[2])

    if command == "all":
        asyncio.run(scrape_all(matchweek))
    elif command == "match-reports":
        fixtures = load_fixtures(matchweek)
        asyncio.run(scrape_match_reports(matchweek, fixtures))
    elif command == "commentary":
        fixtures = load_fixtures(matchweek)
        asyncio.run(scrape_commentary(matchweek, fixtures))
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
