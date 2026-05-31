# Phase 1-5 Expected Results

## Purpose

Use this sheet while running the first five manual verification phases so each step has a clear pass/fail expectation.

## Phase 1: Access And Login

### Step 1

Action:
- Open `@Managrr_Bot` from owner account `8026163028`
- Send `/start`

Expected:
- Bot replies without timeout
- Main reply keyboard appears
- Main sections are visible according to owner access

Fail if:
- No response
- Access denied shown to owner
- Main menu missing

### Step 2

Action:
- Run `/whoami`

Expected:
- Telegram ID is shown correctly
- Owner-level identity/role context is shown

Fail if:
- Wrong Telegram ID shown
- Role data missing or incorrect

### Step 3

Action:
- Run `/my_roles`

Expected:
- Owner or highest effective roles are listed
- No DB error or empty result for owner

Fail if:
- Command errors
- Owner appears role-less

### Step 4

Action:
- Run `/login_code`
- Open [https://empanel.leono.shop](https://empanel.leono.shop)
- Log in with Telegram ID and code

Expected:
- Fresh code is accepted
- Dashboard opens
- Main dashboard cards and tables render

Fail if:
- Code rejected incorrectly
- Login redirects in a loop
- Dashboard opens with a server error

## Phase 2: Channel Approval And Posting

### Step 1

Action:
- Add `@Managrr_Bot` as admin to a test channel

Expected:
- Owner receives pending notification
- Channel appears in `Channels -> Pending`

Fail if:
- No pending notification arrives after a reasonable wait
- Channel is missing from pending list

### Step 2

Action:
- Press `Allow`

Expected:
- Bot verifies access
- Channel becomes `ACTIVE`
- Pending review state clears

Fail if:
- Spinner hangs indefinitely
- Allow action does nothing
- Verification passes but status does not change

### Step 3

Action:
- Open `Channels -> Post`
- Select the approved channel
- Send a test text message

Expected:
- Bot accepts the message
- Message is posted to the selected channel
- No duplicate post appears

Fail if:
- Inactive or wrong channels are shown
- Message never appears
- Post goes to the wrong channel

## Phase 3: Scheduling

### Step 1

Action:
- Open `Channels -> Schedule`
- Select an active channel
- Set a time 1-2 minutes in the future
- Send schedule text

Expected:
- Bot confirms schedule saved
- Entry appears in `/schedule_list`
- Status is pending before execution

Fail if:
- Schedule is rejected without valid reason
- Wrong time interpretation
- Schedule missing from list

### Step 2

Action:
- Wait until scheduled time

Expected:
- Runner posts within normal polling window
- Scheduled post appears in the correct channel
- Schedule status moves to sent/completed

Fail if:
- Nothing posts
- Post goes to wrong target
- Schedule remains stuck pending long after due time

### Step 3

Action:
- Create another schedule
- Cancel it from bot or dashboard

Expected:
- Schedule status becomes canceled
- It does not publish later

Fail if:
- Cancel action claims success but post still sends
- Schedule remains actionable after cancel

## Phase 4: Broadcast

### Step 1

Action:
- Ensure at least two channels are active
- Use `Broadcast -> Select`
- Choose only one target
- Send a test message

Expected:
- Only selected target receives the message
- Unselected active channels do not receive it

Fail if:
- Broadcast goes to all channels
- Selected target does not receive it

### Step 2

Action:
- Use dashboard `Web Broadcast`
- Send a text-only broadcast to selected channels

Expected:
- Dashboard shows success banner
- Delivery Results panel records the event
- Target channels receive the message

Fail if:
- Silent redirect without feedback
- Delivery panel does not update
- Wrong target set receives the message

## Phase 5: Group Approval And Moderation

### Step 1

Action:
- Add the bot as admin to a test group with required permissions

Expected:
- Owner receives pending notification
- Group appears in `Groups -> Pending`

Fail if:
- Notification missing
- Group not listed

### Step 2

Action:
- Approve the group

Expected:
- Status becomes `ACTIVE`
- Group can now appear in moderation and filter menus

Fail if:
- Group remains pending
- Approval says success but menus do not recognize it

### Step 3

Action:
- Open `Groups -> Moderation`
- Select the group
- Press `Lock`

Expected:
- Regular members can no longer send messages
- Bot confirms or reflects lock state

Fail if:
- Lock button does nothing
- Members can still send messages

### Step 4

Action:
- Press `Unlock`

Expected:
- Regular members can send messages again
- Group returns to usable state

Fail if:
- Unlock button does nothing
- Group stays locked

## Result Marking

Mark each step as one of:
- `PASS`
- `FAIL`
- `BLOCKED`

If a step fails, capture:
- exact action
- exact observed result
- approximate time
- whether the same issue happens from bot, dashboard, or both
