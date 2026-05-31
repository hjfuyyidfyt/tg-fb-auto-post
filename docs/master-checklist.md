# Master Checklist

## Current Status

- Core Telegram bot: mostly complete
- Web dashboard: mostly complete
- Server deployment and HTTPS: live
- Shared Oracle isolation: live
- Remaining work: polish, advanced automation, deeper bot controls

## Completed

### Infrastructure

- Ubuntu server deployment
- Docker Compose runtime
- Redis integration
- Oracle dedicated schema with `EM_` prefix isolation
- HTTPS with Nginx
- `empanel.leono.shop` dashboard routing

### Access And Security

- Owner and multi-owner support
- Role-based access control
- Access request approval flow
- Dashboard login code flow
- CSRF protection
- Secure cookies
- Sensitive mode re-auth for destructive actions
- Audit logging

### Telegram Bot Core

- `/start` and role-aware main menu
- Reply keyboard + inline keyboard hybrid UX
- Channels auto-detect and approval
- Groups auto-detect and approval
- Active-only operational model

### Channel Management

- Add/list/approve/block/activate flows
- Channel posting
- Scheduling
- Schedule runner
- Schedule cancel/retry
- Broadcast to all active channels
- Selective broadcast

### Group Management

- Group moderation lock/unlock
- Warnings
- Auto-mute threshold
- Anti-link filter
- Bad-word filter
- Welcome messages
- Join/leave logs

### Bots Module

- Managed bot registry
- Bot status refresh
- Bot config/detail view
- Bot logs view
- Action URL trigger support
- Action auth header and secret support
- Action method and payload template support
- Bot action preview and response capture
- Dashboard-side bot config edit
- Test action without saving
- Built-in and custom bot action presets
- Bot action history panel

### Automation

- Template-based automation rules
- Daily/weekly reports
- Bot health watch
- Pending review watch
- Failed schedule watch
- Automation runner
- Automation dashboard controls
- Automation history and per-rule history
- Custom owner alert rules
- Conditional alert rules
- Multi-trigger conditional rules
- Rule edit/update from dashboard
- Rule duplicate from dashboard
- Rule run-now from dashboard
- Cooldown and quiet-hours support

### Reports And Dashboard

- Daily/weekly/export reports
- Search and status filters
- Stats cards
- Alerts panel
- Recent activity
- Delivery results panel
- Channels/groups/schedules tables
- Schedule history table
- Entity detail pages
- Entity quick actions
- Text exports
- CSV exports
- Web-side broadcast
- Web-side selective broadcast
- Web-side schedule creation
- Media/file support for web broadcast

## Partially Done

- Bots remote control:
  Current state is health check + action URL trigger
  Still missing richer authenticated restart/control workflows

- Automation builder:
  Current state supports templates, custom owner alerts, custom condition alerts,
  multi-trigger rules, duplicate, edit, and run-now
  Still missing multi-step action chains and richer non-owner action targets

- Analytics:
  Current state is operations-oriented summaries
  Still missing deeper channel/group growth analytics

- Delivery visibility:
  Current state is banner feedback + recent delivery logs
  Still missing detailed per-message delivery drilldown

## Remaining High-Value Phases

### Final Polish

- Better empty states and error messages
- Pagination in larger tables
- More compact mobile dashboard polish
- Cleaner success/failure summaries

### Advanced Bots Control

- Authenticated restart endpoints
- More detailed bot health snapshots
- Richer per-bot action responses
- More advanced per-bot action history drilldown and response diffing

### Advanced Automation Builder

- Multi-step actions
- Non-owner action targets
- Richer trigger/action chaining
- Advanced rule editor UI

### Rich Publishing

- Media support for scheduled posts
- Media support for channel direct post from dashboard
- Multi-file/media-group support

### Review And Hardening

- Regression sweep
- Edge-case validation
- Operational cleanup
- Backup/restore drill

### Documentation Wrap-Up

- Admin handbook
- Operator runbook
- Troubleshooting guide

## Practical Completion Estimate

- MVP / main operational system: `92-95%`
- Full platform vision: `80-85%`

## Recommended Next Order

1. Final polish and review pass
2. Media support for scheduled/direct posts
3. Advanced bots control
4. Advanced automation builder
5. Final documentation wrap-up
