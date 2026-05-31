# Reliability Pass

Use this phase to run a quick repeatable regression check after dashboard/bot refactors or deploys.

## Quick command

From the project root:

```powershell
python .\scripts\reliability_check.py --skip-local-health
```

On the server:

```bash
cd /opt/everithing_manager/app
python3 ./scripts/reliability_check.py
```

## What it checks

- Python compile sweep for `app/`
- Telegram Bot API `getMe` when `BOT_TOKEN` is available
- public login/root page
- public dashboard health endpoint
- public unauthenticated dashboard redirect
- public unauthenticated API guard
- local login/root page
- local dashboard health endpoint
- local unauthenticated dashboard redirect
- local unauthenticated API guard

## Defaults

- public URL: `https://empanel.leono.shop`
- local URL: `http://127.0.0.1:8080`

## Optional flags

- `--public-url <url>`
- `--local-url <url>`
- `--skip-local-health`

## Recommended use

Run this after:

- dashboard refactor changes
- deploy/rebuild
- security or session changes
- schedule/broadcast web changes
