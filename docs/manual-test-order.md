# Manual Test Order

## Goal

Run the highest-value manual checks first so the system can be validated quickly after deploys or major feature updates.

## Phase 1: Access And Login

1. Open `@Managrr_Bot` from owner account `8026163028`.
2. Send `/start`.
3. Confirm main menu appears.
4. Run `/whoami`.
5. Run `/my_roles`.
6. Run `/login_code`.
7. Open `https://empanel.leono.shop`.
8. Log in with Telegram ID and login code.
9. Confirm dashboard opens.

## Phase 2: Channel Approval And Posting

1. Add the bot as admin to a test channel.
2. Confirm owner receives pending notification.
3. Open `Channels -> Pending`.
4. Press `Allow`.
5. Open `Channels -> Post`.
6. Select the approved channel.
7. Send a text post.
8. Confirm the message appears in the channel.

## Phase 3: Scheduling

1. Open `Channels -> Schedule`.
2. Select the active test channel.
3. Schedule a post 1-2 minutes ahead.
4. Run `/schedule_list`.
5. Confirm the schedule is listed.
6. Wait for delivery.
7. Confirm the scheduled message is posted.
8. Create another schedule.
9. Cancel it from bot or dashboard.
10. Confirm it does not post.

## Phase 4: Broadcast

1. Ensure at least two active channels exist.
2. Open `Broadcast -> Select`.
3. Choose only one target.
4. Send a broadcast.
5. Confirm only the selected channel receives it.
6. Use dashboard `Web Broadcast`.
7. Send a text-only broadcast to selected channels.
8. Confirm delivery and dashboard banner.

## Phase 5: Group Approval And Moderation

1. Add the bot as admin to a test group with delete/restrict permissions.
2. Confirm owner receives pending notification.
3. Approve the group.
4. Open `Groups -> Moderation`.
5. Press `Lock`.
6. Confirm regular members cannot send messages.
7. Press `Unlock`.
8. Confirm regular members can send messages again.

## Phase 6: Filters And Warnings

1. Open `Groups -> Filters`.
2. Enable `Anti-Link`.
3. Send a link from a non-admin test account.
4. Confirm deletion.
5. Reply to a member message with `/warn`.
6. Confirm warning count increases.
7. Trigger enough warnings to test auto mute.

## Phase 7: Welcome And Logs

1. Open `Groups -> Welcome`.
2. Enable welcome and join logs.
3. Run `/setwelcome Welcome {member} to {group}`.
4. Add a new member.
5. Confirm welcome and join log messages.
6. Remove that member.
7. Confirm leave log message.

## Phase 8: Dashboard Sensitive Actions

1. Use `/login_code` again.
2. Unlock `Sensitive Mode`.
3. Try `Block` on a test pending or active entity.
4. Try schedule `Cancel` or `Retry`.
5. Confirm protected actions work only after unlock.

## Phase 9: Automation

1. Create a temporary automation rule from bot or dashboard.
2. Pause it.
3. Activate it again.
4. Delete it.
5. Confirm history entries appear.

## Phase 10: Exports

1. Download one text export.
2. Download one CSV export.
3. Confirm the files open and contain expected data.

## Fast Pass Completion Rule

If Phases 1 through 5 pass cleanly, the system has strong basic operational confidence.

If all 10 phases pass, the current release can be treated as highly confidence-checked for normal admin use.
