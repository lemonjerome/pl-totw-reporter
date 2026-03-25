# English Premier League — Team of the Week Builder

Automated EPL TOTW system. Fetches 2025-26 match data via soccerdata (FPL + Understat + ESPN), scrapes the PL website for match reports and commentaries, selects the best formation and players, generates a visual team diagram, creates a Google Slides presentation, and delivers results via Gmail.

## Project Details

- **From email**: 24hrnts@gmail.com
- **To email**: 20gabramos04@gmail.com
- **Data source**: `soccerdata` library — FPL API (fixtures) + Understat (attacking stats) + ESPN (saves/formation). No API key required.
- **API-Football**: Legacy — covers seasons 2022–2024 only. Use `scripts/api_football.py` for historical data. Script: `scripts/soccerdata_client.py` for 2025-26.
- **PL website**: https://www.premierleague.com

## Tech Stack

- Python 3.11+ — all data processing, API calls, scraping, rendering
- Playwright — PL website scraping (JS-heavy SPA) + HTML-to-PNG screenshots
- Jinja2 — HTML templating for diagram and email
- Pydantic — data models
- Google Workspace MCP — Google Slides + Gmail
- Playwright MCP — web browsing by agents

## Key Conventions

**2025-26 data**: Always use `scripts/soccerdata_client.py`. It combines FPL API + Understat + ESPN, caches to `data/2025-26/matchweek-{N}/` in API-Football format. No daily budget.

**Historical data (2022-24)**: Use `scripts/api_football.py`. Handles rate limiting (100 req/day) and caches responses.

**Caching**: All data cached in `data/2025-26/matchweek-{N}/`. All generated outputs in `output/matchweek-{N}/`.

**Rate limit tracking**: `data/.api_usage.json` tracks daily API-Football usage (legacy only).

**Domain knowledge**: All football rules, formations, position roles, API docs, and design specs live in `.claude/rules/`. Agents load these automatically.

**Environment**: Secrets in `.claude/settings.local.json` (gitignored). See `.env.example` for required vars.

## Quick Commands

```bash
# Fetch matchweek data (2025-26)
python scripts/soccerdata_client.py fetch-round 30

# Run analysis
python scripts/formation_analyzer.py 30
python scripts/player_evaluator.py 30

# Generate diagram
python scripts/diagram_renderer.py 30

# Scrape PL website
python scripts/pl_scraper.py match-reports 30

# Run tests
pytest tests/ -v
```

## Invoking the TOTW Builder

In Claude Code chat:
```
/totw 30           # Build TOTW for matchweek 30
/totw              # Build TOTW for the latest completed matchweek
/research 30       # Fetch data only
/analyze 30        # Analyze data only (requires research done)
/visualize 30      # Generate diagram only
/presentation 30   # Create slides only
/email 30          # Send email only
```

## Agent Delegation

- **@researcher** — data collection (soccerdata: FPL+Understat+ESPN), PL website scraping, formation analysis, player selection, synthesis reports
- **@visualizer** — team diagram PNG, Google Slides presentation, PDF export, Gmail delivery

## Project Structure

```
scripts/       Python scripts for each pipeline stage
templates/     Jinja2 HTML templates (pitch diagram, email)
data/          Cached API data per matchweek (gitignored)
output/        Generated outputs per matchweek (gitignored)
tests/         pytest unit tests
.claude/       Claude Code config: agents, rules, skills
```

## Git Workflow

- Branch off `main` for features
- Descriptive commit messages
- Never commit: `.env`, `settings.local.json`, `data/`, `output/`
