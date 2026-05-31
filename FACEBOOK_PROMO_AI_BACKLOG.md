# Facebook & Telegram AI Social Media Manager Backlog

Last updated: 2026-05-26

## Current Status

The core autonomous Social Media Manager bot and multi-platform upgrade for both Facebook Pages and Telegram channels/groups are fully coded, deployed to production, and actively running.

- Facebook Page ID and Page access token are saved and active.
- Telegram channel/group auto-activation is active.
- AI chat manager manages both Facebook Page and active Telegram channels/groups.
- The bot successfully polls in production without errors.

## Completed Features & Upgrades

### 1. Autonomous AI Chatbox (Phase 1 to 5)
- **AI Memory & Logging:** Created SQL migration (`sql/011_init_em_ai_memory.sql`) with `EM_AI_PREFERENCES` (stores AI rules) and `EM_AI_LOGS` (logs publishing/scheduling actions), backed by a Python repository `app/repositories/ai_memory.py`.
- **Gemini Tool-Calling Agent:** Custom `AIAssistantAgent` in `app/services/ai_agent.py` executes python function tools recursively, with a robust 3-attempt backoff retry logic (targeting 503/429 limits).
- **Session Media Handling:** Supports direct photo messages (`F.photo`) in AI chat; downloads media and saves metadata in Redis (`fbpromo_chat_media:{user_id}`) to attach to scheduled or published posts.
- **Multipart Photo Publishing:** `publish_post` performs custom multipart/form-data binary upload directly to Facebook Graph API for photo posts.
- **Auto-Scheduler (ScheduleRunner):** Upgraded `ScheduleRunner` in `app/services/schedule_runner.py` to automatically publish text and photo posts to Facebook when they become due.
- **Database Bug Fix (ORA-01745):** Renamed `:uid` to `:user_id` in `schedule_runner.py` to avoid Oracle reserved keyword errors.

### 2. Multi-Platform AI Telegram Management Upgrade (NEW!)
- **Zero-Hassle Auto-Activation:**
  - Upgraded `detect_entity` in `app/services/entities.py` to support `added_by_user_id` and custom statuses.
  - Refactored `bot_chat_membership_handler` in `app/handlers/navigation.py` to lookup the Telegram User ID of administrators who add the bot to a channel or group.
  - Auto-activates the channel/group (`status = "ACTIVE"`) if the user is registered in `EM_USERS`, sending a beautiful confirmation message in Bangla HTML. Only falls back to pending review if the user is unknown.
- **Destination Resolution (`list_targets`):**
  - Registered `list_targets()` function tool in `ai_agent.py`.
  - Implemented `list_targets` callback in `facebook_promo_chat.py` to dynamically fetch the user's Facebook Page and all active Telegram channels and groups from the database.
- **Immediate Multi-Platform Publishing:**
  - Upgraded `publish_post` schema and handler to accept `target_id`.
  - If target is a Telegram channel/group, uses Telegram's send methods (`send_message`, `send_photo`, `send_video`, `send_audio`, `send_document`) to publish the text and session-uploaded media instantly.
- **Out-of-the-Box Telegram Scheduling:**
  - Upgraded `schedule_future_post` handler to support `target_id`.
  - Looks up the channel/group title from the database and inserts the post into `EM_SCHEDULED_POSTS` with `CHANNEL_IDENTIFIER = target_id`.
  - The backend `ScheduleRunner` automatically routes scheduled Telegram posts using Telegram APIs for non-Facebook channel identifiers.
- **Context-Aware Master System Prompt:** Refactored the prompt in `facebook_promo_chat.py` to guide the AI on calling `list_targets` to discover destinations and mapping user destination references to their IDs.

## Production Status & Next Steps

### 1. Active Deployment Verification
- All 4 modified files (`entities.py`, `navigation.py`, `ai_agent.py`, `facebook_promo_chat.py`) are fully deployed to `/opt/everithing_manager/app/app/` on production.
- Docker container `everithing_manager_bot` is restarted and active.
- Logs show polling and database operations are working smoothly.

### 2. Testing Instructions
1. Add the bot as an administrator to a test channel or group. Check that it sends a private confirmation message instantly in Bangla.
2. Open AI Chat via "💬 Start Promo Chat (Auto)", and ask: *"আমার কোন কোন চ্যানেল কানেক্ট করা আছে?"*. Verify that both Facebook Page and your new Telegram channel are listed.
3. Test direct publishing: Upload a photo, and say: *"আমাদের সেল অফারটা [টেলিগ্রাম চ্যানেলের নাম] চ্যানেলে পোস্ট করে দাও"*
4. Test scheduling: Say: *"এই পোস্টটা কাল বিকেল ৪ টায় [টেলিগ্রাম চ্যানেলের নাম] এ শিডিউল করো"*.
