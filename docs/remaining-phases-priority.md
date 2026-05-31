# Remaining Phases Priority

## Current Status

The main operations platform is already in a strong usable state.

Practical estimate:
- Core operational system: `90%+`
- Full polished platform vision: `75-80%`

## Priority 1: Recurring Schedule Controls

Why first:
- Recurring schedules are now supported, but management controls are still basic.
- This is the most immediate follow-up to the latest scheduling work.

Recommended additions:
- Pause recurring schedule
- Resume recurring schedule
- Edit recurring schedule timing
- Skip next occurrence
- Better recurring schedule labels in bot and dashboard

## Priority 2: Media Scheduling

Why second:
- Media broadcast already exists on web.
- Scheduling still needs richer publishing support.

Recommended additions:
- Schedule photo posts
- Schedule document/file posts
- Caption support
- Media preview in dashboard history if practical

## Priority 3: Reliability And Regression Safety

Why third:
- The system is already large enough that reliability now matters more than feature count.

Recommended additions:
- Repeatable regression checklist by module
- Optional lightweight automated smoke tests
- Better error logging around schedule execution and bot actions
- Crash-path review for runner tasks

## Priority 4: Dashboard Refactor

Why fourth:
- `app/web.py` is now feature-rich but large.
- Future changes will be safer if it is split.

Recommended additions:
- Move dashboard routes into smaller modules
- Separate rendering helpers from request handlers
- Centralize dashboard HTML fragments

## Priority 5: Advanced Bots Module

Why fifth:
- Existing bot registry/status/actions are useful already.
- Next value comes from deeper integration, not basic CRUD.

Recommended additions:
- Authenticated restart payloads
- Richer action payload templates
- External log source integration
- Better per-bot incident history

## Priority 6: Advanced Automation Builder

Why sixth:
- Template-based automation is already usable.
- Full custom automation is valuable but not the most urgent item.

Recommended additions:
- Trigger-condition-action builder
- Entity status trigger rules
- Schedule failure remediation workflows
- Approval reminder workflows with customization

## Priority 7: Documentation Polish

Why seventh:
- Docs already exist, but operator-facing usage docs can still be improved.

Recommended additions:
- Admin handbook
- Operator quick-start guide
- Troubleshooting guide
- Backup and recovery notes

## Recommended Next Order

1. Recurring schedule controls
2. Media scheduling
3. Reliability pass
4. Dashboard refactor
5. Advanced bots module
6. Advanced automation builder
7. Documentation polish
