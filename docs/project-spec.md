# Project Spec

## Product Goal

Build a Telegram control hub that helps one owner or a trusted admin team manage:

- Telegram channels
- Telegram groups
- Connected Telegram bots
- Broadcasts and schedules
- Admin roles, logs, and automation

## UX Direction

Main navigation uses `Reply Keyboard`.

Sub-actions use `Inline Keyboard`.

This keeps the interface persistent, clean, and easier to learn.

## Main Sections

- `Channels`
- `Groups`
- `Bots`
- `Automation`
- `Reports`
- `Settings`

## MVP Scope

### Included

- Owner authentication
- Role-based admin access
- Home menu with reply keyboard
- Section landing screens with inline actions
- Channel registration
- Group registration
- Scheduled posts metadata
- Broadcast job creation
- Audit logging
- Oracle-backed persistent storage
- Redis-backed temporary state and queue helpers

### Deferred

- Full analytics
- Advanced multi-bot lifecycle control
- AI content generation
- Web dashboard
- Billing or SaaS multi-tenancy

## Roles

- `Owner`
- `Super Admin`
- `Channel Manager`
- `Group Manager`
- `Moderator`
- `Viewer`

## High-Level Constraints

- No local runtime/testing/storage for the bot
- All runtime services must execute on the server
- Shared Oracle environment must not mix data with other apps
- Sensitive actions require confirmation and auditing

## Core Principles

- Keep top-level navigation stable
- Keep actions contextual
- Keep permissions explicit
- Keep every sensitive action auditable
- Keep deployment reproducible
