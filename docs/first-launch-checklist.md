# First Launch Checklist

## Secrets To Fill On The Server

Edit `/opt/everithing_manager/app/.env` and set:

- `BOT_TOKEN`
- `BOT_OWNER_ID`
- `ORACLE_USER`
- `ORACLE_PASSWORD`
- `ORACLE_DSN=peb11wp11w4qg69w_tp`

Keep:

- `ORACLE_WALLET_DIR=/opt/everithing_manager/config/oracle-wallet`
- `REDIS_URL=redis://redis:6379/0`

## Oracle Isolation Steps

1. Stay on the same shared Oracle database used by your other apps.
2. Connect to that shared Oracle environment as an admin account.
3. Run [000_oracle_schema_setup.sql](C:/Anti%20Gravity/everithing_manager/sql/000_oracle_schema_setup.sql) to create a dedicated bot schema/user.
4. Connect as `EVERYTHING_MANAGER_APP`.
5. Run [001_init_em_core.sql](C:/Anti%20Gravity/everithing_manager/sql/001_init_em_core.sql).

This setup keeps the bot in the same DB environment while isolating it with:

- a dedicated schema/user
- `EM_` prefix on all objects

## First Live Start

On the server:

```bash
cd /opt/everithing_manager/app
sudo docker compose up -d
sudo docker compose logs -f bot
```

## Expected First-Run Behavior

- owner sends `/start`
- bot upserts the owner user
- bot ensures default roles exist
- bot auto-assigns `OWNER` role to the configured owner ID
- audit logs start recording navigation events

## Before Real Group/Channel Testing

- create a separate test bot token if possible
- create one test group
- create one test channel
- add the bot as admin where needed
- avoid testing in production chats first
