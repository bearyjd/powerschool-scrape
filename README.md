# ps — PowerSchool Parent Portal CLI

Scrapes the PowerSchool parent portal (set `PS_BASE_URL` to your district's PowerSchool URL) for
each child's **missing**, **late** and **upcoming** assignments. Built for a cron agent: JSON on
stdout, logs on stderr.

## Setup

```bash
pip install -e '.[browser,dev]'
playwright install chromium
```

Playwright is only imported at login time (the portal needs a real browser login).

## Credentials

Priority: env vars > `~/.powersched/.env` (should be `chmod 600`; a warning is logged otherwise).

| Variable | Required | Default |
|---|---|---|
| `PS_USERNAME` | yes | |
| `PS_PASSWORD` | yes | |
| `PS_BASE_URL` | **yes** | e.g. `https://yourdistrict.powerschool.com` (https, `*.powerschool.com` only) |

The file may be `KEY=VALUE` lines (see `.env.example`) or the legacy 2-line form: line 1
username, line 2 password.

## Usage

```
powerschool summary --json [--days N] [--child NAME]
```

`--days` = upcoming window (default 14). `--child` = case-insensitive name substring.

## JSON contract

```json
{"scraped_at": "ISO8601",
 "children": [{"name": "", "student_id": "", "missing": [A], "late": [A],
               "upcoming": [A], "warnings": [""]}],
 "warnings": [""]}
```
`A = {"course", "title", "due": "YYYY-MM-DD", "category": str|null, "score": str|null}`

- missing: score record `ismissing` and not exempt. late: `islate` and not exempt.
- upcoming: due between today and today+N, not collected / scored / exempt / missing.
- Deduped, sorted by due date. Per-child problems go in `children[].warnings` only; top-level `warnings` is reserved for run-wide problems (e.g. no students found, no `--child` match), so any top-level warning means an untrusted scrape.
- Login/config failure: exit 1 with `{"error": "...", "warnings": []}` on stdout.

## Tests

```bash
pytest -q --cov=ps_cli
```
