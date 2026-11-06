# CLAUDE.md — powerschool-scrape (ps)

Sibling of `schoology-scrape`. Python CLI `powerschool` (package `ps_cli`; not named `ps`, which shadows the system process command) scraping the PowerSchool
parent portal; consumed by a cron agent via `powerschool summary --json` (stdout JSON only, logs to stderr).

## Commands
```bash
pip install -e '.[browser,dev]' && playwright install chromium
pytest -q --cov=ps_cli     # no network / creds needed
```

## Layout
- `ps_cli/parse.py` pure parsers (`classify`, `parse_students`, `parse_class_links`, `parse_course_name`)
- `ps_cli/config.py` credentials (env > `~/.powersched/.env`; KEY=VALUE or legacy 2-line)
- `ps_cli/browser.py` Playwright login + per-class capture (lazy import)
- `ps_cli/summary.py` builds the contract dict; `ps_cli/cli.py` argparse + `output()`
- `tests/fixtures/` SYNTHETIC data only (Alex/Sam/Jo). Never commit real names/titles/scores.

## How the site works
- Login: `{base}/public/`, `#fieldAccount`, `#fieldPassword`, `#btn-enter-sign-in` -> `/guardian/home.html`.
- Students: `javascript:switchStudent(<id>);` anchors on home; call it in page context.
- Class pages: `a[href*='scores.html?frn=']` containing `begdate=`. Loading one fires
  `POST /ws/xte/assignment/lookup`; we capture that response (list of assignments, dates `YYYY-MM-DD`).
  Course name comes from the first cell of the `Course` table in the page DOM.

## Rules
- NEVER print/log/commit credentials; errors carry exception class only. No student names in INFO logs.
- Per-child problems -> `children[].warnings` ONLY. Top-level `warnings` = run-wide problems only
  (the dashboard treats any top-level warning as an untrusted scrape).
- `PS_BASE_URL` must be https on `*.powerschool.com` (or exactly `PS_ALLOWED_HOST`); the browser
  re-checks the host before typing credentials and after login. Credentials never go elsewhere.
- No district is hard-coded: `PS_BASE_URL` is required (env or `~/.powersched/.env`), so the repo carries nothing school-specific.
- Cred file: mode != 600 or foreign owner only WARNS (Docker mounts), never fails.
- Immutable data (frozen dataclasses), files < 400 lines.
