# Oracle Isolation Plan

## Recommended Workload

Use Oracle `Transaction Processing` for this bot.

Reason:

- frequent small writes
- role and permission checks
- schedules and audit logs
- chat and entity metadata
- job state updates

## Isolation Strategy

This project is designed for:

- the same shared Oracle database
- a dedicated schema/user for this bot
- `EM_` prefix on all bot-owned objects

This means:

- not a separate Oracle database
- not mixing bot tables into another app's schema
- not prefix-only isolation unless you explicitly choose that fallback later

## Required Rules

- Use the existing shared Oracle database
- Create a dedicated schema, for example `EVERYTHING_MANAGER_APP`
- Grant only required privileges to this schema
- Never store bot data in another app schema
- Prefix bot-owned objects with `EM_`
- Keep migrations separate from all other apps

## Why This Is Better Than Prefix-Only

Prefix-only isolation in a shared schema can work, but dedicated schema plus prefix is safer because:

- permissions stay cleaner
- accidental cross-app queries are less likely
- migrations are easier to reason about
- cleanup and backup boundaries are clearer

## Suggested Naming

- `EM_USERS`
- `EM_ADMINS`
- `EM_ROLES`
- `EM_USER_ROLES`
- `EM_CHANNELS`
- `EM_GROUPS`
- `EM_BOTS`
- `EM_BROADCAST_JOBS`
- `EM_SCHEDULED_POSTS`
- `EM_AUDIT_LOGS`
- `EM_SETTINGS`

## Redis Responsibility

Redis should be used for:

- FSM state
- throttling
- distributed locks
- queue coordination
- short-lived job metadata

Oracle should be used for:

- durable business data
- permissions
- schedules
- audit logs
- managed Telegram entities
