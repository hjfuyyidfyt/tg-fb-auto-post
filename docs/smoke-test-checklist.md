# Smoke Test Checklist

## Goal

Use this checklist after major changes, deploys, or infra updates to confirm that the bot and dashboard still work end to end.

## Pre-Checks

- Confirm bot container is running.
- Confirm dashboard container is running.
- Confirm Redis is running.
- Confirm Oracle connectivity is healthy.
- Confirm `https://empanel.leono.shop/healthz` returns `200`.
- Confirm bot responds to `/start` from an owner account.

## Bot Access

- Send `/start` from owner account `8026163028`.
- Send `/start` from owner account `7020461098`.
- Confirm main menu renders.
- Run `/whoami`.
- Run `/my_roles`.
- Run `/admins`.
- Confirm role-restricted user only sees allowed menu items.

## Access Requests

- From a non-owner account, run `/request_access VIEWER`.
- Confirm owner receives approval request.
- Approve the request.
- Confirm requester receives approval message.
- Confirm requester can now use `/start`.
- Revoke the role if this was only a test.

## Channel Detection And Approval

- Add `@Managrr_Bot` as admin to a fresh test channel.
- Confirm owner receives pending channel notification.
- Open `Channels -> Pending`.
- Confirm the channel appears in the pending list.
- Press `Allow`.
- Confirm status becomes `ACTIVE`.
- Remove the bot from the channel.
- Confirm status changes to `REMOVED` or owner receives removal notice.

## Group Detection And Approval

- Add `@Managrr_Bot` as admin to a fresh test group.
- Confirm owner receives pending group notification.
- Open `Groups -> Pending`.
- Confirm the group appears in the pending list.
- Press `Allow`.
- Confirm status becomes `ACTIVE`.
- Remove the bot from the group.
- Confirm status changes to `REMOVED` or owner receives removal notice.

## Channel Posting

- Ensure at least one channel is `ACTIVE`.
- Open `Channels -> Post`.
- Select an `ACTIVE` channel.
- Send a text message.
- Confirm the message appears in the target channel.

## Scheduling

- Open `Channels -> Schedule`.
- Select an `ACTIVE` channel.
- Schedule a post 1-2 minutes ahead.
- Confirm schedule is saved.
- Run `/schedule_list`.
- Confirm the pending schedule appears.
- Wait for execution.
- Confirm scheduled post is delivered.
- Create another schedule and cancel it.
- Confirm canceled schedule does not execute.

## Broadcast

- Ensure multiple channels are `ACTIVE`.
- Open `Broadcast -> Targets`.
- Confirm active targets list is correct.
- Run `Broadcast -> Send All`.
- Send a test message.
- Confirm delivery to all `ACTIVE` channels.
- Run `Broadcast -> Select`.
- Select only a subset of channels.
- Compose and send another message.
- Confirm delivery only to selected targets.

## Group Moderation

- Ensure an `ACTIVE` group exists with proper admin permissions.
- Open `Groups -> Moderation`.
- Select the group.
- Press `Lock`.
- Confirm regular members cannot send messages.
- Press `Unlock`.
- Confirm regular members can send messages again.

## Warnings

- In an `ACTIVE` group, reply to a member message with `/warn`.
- Confirm warning count increases.
- Run `/warnings` in reply to the same user.
- Confirm count is shown.
- Warn the user up to the mute threshold.
- Confirm auto mute happens when threshold is reached.
- Open `Groups -> Warnings`.
- Confirm warning leaderboard is visible.
- Press `Reset All`.
- Confirm warnings are cleared.

## Filters

- Open `Groups -> Filters`.
- Enable `Anti-Link`.
- Send a link from a non-admin user.
- Confirm the message is deleted.
- Add a custom bad word with `/addbadword testword`.
- Send that word from a non-admin user.
- Confirm the message is deleted.
- Run `/badwords`.
- Confirm custom list is visible.
- Remove the word with `/removebadword testword`.

## Welcome And Logs

- Open `Groups -> Welcome`.
- Enable welcome and join logs.
- Run `/setwelcome Welcome {member} to {group}`.
- Add a new test member.
- Confirm welcome message appears.
- Confirm join log appears.
- Remove that member.
- Confirm leave log appears.

## Bots Module

- Open `Bots -> Actions`.
- Add a test managed bot entry.
- Open `Bots -> Status`.
- Confirm the bot appears.
- Open `Bots -> Configs`.
- Confirm stored metadata appears.
- Open `Bots -> Logs`.
- Confirm recent activity appears.
- If an action URL exists, press `Run Action`.
- Confirm result is recorded.

## Automation

- Open `Automation -> Templates`.
- Create a `Daily Report Delivery` rule.
- Open `Automation -> Rules`.
- Confirm the rule is listed.
- Pause the rule.
- Confirm status changes.
- Activate it again.
- Delete the rule if it was only for testing.
- Confirm automation events appear in history.

## Reports

- Open `Reports -> Daily`.
- Open `Reports -> Weekly`.
- Open `Reports -> Export`.
- Confirm values look coherent with current system state.

## Dashboard Login

- Run `/login_code`.
- Visit `https://empanel.leono.shop`.
- Log in with Telegram ID and code.
- Confirm dashboard opens.
- Confirm `Logout` works.

## Dashboard Search And Tables

- Log back in.
- Use the search field.
- Use the status filter.
- Confirm `Managed Channels`, `Managed Groups`, and `Scheduled Posts` react correctly.
- Open a channel detail page.
- Open a group detail page.
- Confirm recent activity is visible.

## Dashboard Sensitive Mode

- Open `Sensitive Mode`.
- Unlock with a fresh `/login_code`.
- Confirm unlock succeeds.
- Confirm protected actions can now run.
- Wait for expiry or log out and back in.
- Confirm protected actions require unlock again.

## Dashboard Broadcast

- Use `Web Broadcast`.
- Send a text-only broadcast to selected channels.
- Confirm top banner shows result.
- Confirm `Delivery Results` panel records it.
- Send a media/file broadcast.
- Confirm file or image is delivered correctly.

## Dashboard Schedule

- Use `Web Schedule`.
- Create a scheduled message for an `ACTIVE` channel.
- Confirm success banner appears.
- Confirm schedule appears in `Scheduled Posts`.
- Cancel or retry from dashboard as applicable.
- Confirm `Schedule History` records the action.

## Dashboard Entity Actions

- Open a pending entity detail page.
- Test `Allow`, `Ignore`, or `Block`.
- Confirm status changes.
- Confirm entity activity shows the action.
- Confirm `Block` requires sensitive mode.

## Dashboard Automation

- Create an automation rule from dashboard.
- Pause it.
- Activate it.
- Delete it.
- Confirm both global automation history and per-rule history update.

## Exports

- Download text exports.
- Download CSV exports.
- Confirm files open and contain expected columns/data.

## Security Regression Checks

- Try accessing a protected dashboard POST endpoint without being logged in.
- Confirm redirect to login or denial.
- Try a destructive action without sensitive mode.
- Confirm it is blocked.
- Try invalid `next` or `next_url` values.
- Confirm redirect stays local.
- Try oversized upload above 10 MB.
- Confirm the upload is rejected cleanly.

## Final Sign-Off

- Confirm no critical flow failed.
- Record any broken or flaky behavior.
- Fix blockers before the next production-only rollout.
