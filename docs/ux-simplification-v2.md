# UX Simplification V2

This plan makes `everithing_manager` easier to use without removing any existing feature, module, or future expansion path.

## Goal

- Keep all current power features.
- Reduce first-screen complexity.
- Push rare/technical controls one level deeper.
- Make common tasks feel step-by-step instead of overwhelming.

## Core Principle

Use progressive disclosure:

- show the simplest actions first
- show deeper tools only when the user asks for them
- keep all existing sections and callbacks alive underneath

## Current UX Problem

The current bot is powerful, but it exposes too many concepts too early:

- too many top-level sections
- technical sections mixed with everyday actions
- users must remember where posting, scheduling, review, and broadcast live
- advanced tools feel equal to common tasks

## V2 Navigation Model

### Reply Keyboard

Keep the reply keyboard focused on only 7 items:

- `🏠 Home`
- `⚡ Quick`
- `📢 Channels`
- `👥 Groups`
- `🤖 Bots`
- `📊 Reports`
- `⚙️ Advanced`

### What Changed

- `Broadcast` is no longer top-level.
- `Automation` is no longer top-level.
- `Settings` is no longer top-level.

Nothing is removed:

- `Broadcast` stays reachable from `Home`, `Quick`, and `Advanced`
- `Automation` stays reachable from `Advanced`
- `Settings` stays reachable from `Advanced`

## Layering Strategy

### Layer 1: Home

Purpose:

- safe starting point
- overview + common shortcuts

Buttons:

- `✅ Review Pending`
- `📝 Quick Post`
- `⏰ Quick Schedule`
- `📤 Broadcast`
- `⚙️ Advanced`

### Layer 2: Quick

Purpose:

- fastest path for repeat daily tasks

Buttons:

- `📝 Quick Post`
- `⏰ Quick Schedule`
- `✅ Review Pending`
- `📤 Broadcast`
- `🚨 Alerts`

### Layer 3: Main Sections

Purpose:

- full contextual control per domain

Examples:

- `📢 Channels` → Add, Pending, List, Post, Schedule, Analytics
- `👥 Groups` → Add, Pending, List, Moderation, Warnings, Filters, Welcome
- `🤖 Bots` → Status, Logs, Configs, Actions
- `📊 Reports` → Daily, Weekly, Export

### Layer 4: Advanced

Purpose:

- keep power features available without cluttering normal flow

Buttons:

- `⚙️ Automation`
- `🛠️ Settings`
- `📤 Broadcast`
- `🤖 Bots`
- `📊 Reports`

## No-Feature-Removed Mapping

| Old Top Level | New Entry Point |
| --- | --- |
| Channels | `📢 Channels` |
| Groups | `👥 Groups` |
| Broadcast | `⚡ Quick` or `⚙️ Advanced` |
| Bots | `🤖 Bots` or `⚙️ Advanced` |
| Automation | `⚙️ Advanced` |
| Reports | `📊 Reports` or `⚙️ Advanced` |
| Settings | `⚙️ Advanced` |

## Copy And Tone Improvements

### New Rules

- one screen = one task
- short instructions
- better action names
- friendly wording
- emoji-assisted scanning

### Examples

Instead of:

- `Available actions: Add, Pending, List, Post, Schedule`

Use:

- `Choose one action below.`

Instead of:

- `Choose a main section from the reply keyboard below.`

Use:

- `Keep things simple from here. Use ⚡ Quick for common tasks.`

## Phase Plan

### Phase 1: Navigation Simplification

Deliverables:

- new reply keyboard
- `Home`, `Quick`, `Advanced` layers
- advanced sections moved one level deeper
- no feature removal

### Phase 2: Section Copy Cleanup

Deliverables:

- cleaner headings
- shorter prompts
- more consistent wording
- better action labels with emoji

### Phase 3: Review Hub

Deliverables:

- unified pending review screen
- cleaner approval UX
- less noisy pending cards

### Phase 4: Schedule UX Refresh

Deliverables:

- schedule type first
- clearer time choices
- easier recurring explanation
- confirm screen before save

### Phase 5: Channel And Group Wizard Flows

Deliverables:

- target selection
- action selection
- input step
- confirm step

### Phase 6: Advanced Segmentation

Deliverables:

- technical actions grouped more clearly
- diagnostics and raw tools further tucked away
- cleaner owner/operator split

## Success Criteria

V2 is successful when:

- new users understand where to start immediately
- common tasks take fewer taps
- powerful features still exist
- owners still retain full control
- the bot feels lighter without becoming weaker

## Immediate Implementation Order

1. ship the new layered main menu
2. add `Home`, `Quick`, and `Advanced` shortcut keyboards
3. keep existing section handlers intact behind the new entry points
4. clean copy and emoji labels
5. iterate on review and schedule UX next
