# everithing_manager

`everithing_manager` is a Telegram operations bot for centrally managing channels, groups, and connected bots through a clean hybrid navigation model:

- Reply Keyboard for top-level sections
- Inline Keyboard for contextual actions

The project is being built with a server-first workflow:

- Development artifacts can live in this workspace
- Runtime, testing, storage, logs, and databases must run on the target server
- Oracle is the primary relational database, isolated under a dedicated schema for this bot

## Initial stack

- Python
- Aiogram
- Oracle Database (`Transaction Processing` workload recommended)
- Redis for queue/state/caching
- Docker Compose for deployment

## Core sections

- Channels
- Groups
- Bots
- Automation
- Reports
- Settings

## Documentation

- [Project Spec](C:/Anti%20Gravity/everithing_manager/docs/project-spec.md)
- [Execution Roadmap](C:/Anti%20Gravity/everithing_manager/docs/execution-roadmap.md)
- [Master Checklist](C:/Anti%20Gravity/everithing_manager/docs/master-checklist.md)
- [Final Review](C:/Anti%20Gravity/everithing_manager/docs/final-review.md)
- [Completion Review 2026-04-20](C:/Anti%20Gravity/everithing_manager/docs/completion-review-2026-04-20.md)
- [Smoke Test Checklist](C:/Anti%20Gravity/everithing_manager/docs/smoke-test-checklist.md)
- [Manual Test Order](C:/Anti%20Gravity/everithing_manager/docs/manual-test-order.md)
- [Phase 1-5 Expected Results](C:/Anti%20Gravity/everithing_manager/docs/phase-1-5-expected-results.md)
- [Remaining Phases Priority](C:/Anti%20Gravity/everithing_manager/docs/remaining-phases-priority.md)
- [Reliability Pass](C:/Anti%20Gravity/everithing_manager/docs/reliability-pass.md)
- [Maintenance Runbook](C:/Anti%20Gravity/everithing_manager/docs/maintenance-runbook.md)
- [Stable Handoff](C:/Anti%20Gravity/everithing_manager/docs/stable-handoff.md)
- [Regression Tests](C:/Anti%20Gravity/everithing_manager/docs/regression-tests.md)
- [UX Simplification V2](C:/Anti%20Gravity/everithing_manager/docs/ux-simplification-v2.md)
- [Server Deployment Notes](C:/Anti%20Gravity/everithing_manager/docs/server-deployment.md)
- [Oracle Isolation Plan](C:/Anti%20Gravity/everithing_manager/docs/oracle-isolation.md)
- [First Launch Checklist](C:/Anti%20Gravity/everithing_manager/docs/first-launch-checklist.md)
"# tg-fb-auto-post" 
