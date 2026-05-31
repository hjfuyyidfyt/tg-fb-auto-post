# Stable Handoff

## Live endpoints

- Bot: `@Managrr_Bot`
- Dashboard: `https://empanel.leono.shop`

## Core status

- bot: live
- dashboard: live
- redis: live
- HTTPS: live
- Oracle-backed app data: live
- role-based access: live
- maintenance scripts: ready

## Best daily-use flow

1. use the Telegram bot for quick channel, group, broadcast, and moderation actions
2. use the dashboard for:
   - deeper review
   - automation management
   - bot diagnostics
   - schedule control
   - exports

## Fast maintenance commands

- unit tests:
  - `python -m unittest discover -s tests -v`
- reliability only:
  - `python scripts/reliability_check.py`
- full check:
  - `python scripts/full_check.py`

## Server-side fast maintenance

- app path:
  - `/opt/everithing_manager/app`
- common commands:
  - `cd /opt/everithing_manager/app`
  - `sudo docker compose up -d --build`
  - `python3 scripts/reliability_check.py`
  - `python3 scripts/full_check.py`

## If something looks broken

1. run `python3 scripts/reliability_check.py`
2. if it was right after a deploy and you see temporary `502`, rerun once after a short wait
3. run `python3 scripts/full_check.py`
4. inspect:
   - `sudo docker compose ps`
   - `sudo docker compose logs --tail=100 bot dashboard`

## High-value dashboard areas

- `Action Center`
- `Ops Snapshot`
- `Automation Insights`
- `Scheduled Posts`
- `Managed Bots`

## Current strong-use scope

- channel/group approval and management
- posting, broadcast, one-time and recurring schedule flows
- group moderation, warnings, filters, welcome/logging
- bot registry, action testing, payload preview, presets
- template and custom automation rules
- dashboard exports and ops reporting

## Still-expandable areas

- richer analytics
- deeper external bot integrations
- advanced multi-step automation chains
- larger regression suite
