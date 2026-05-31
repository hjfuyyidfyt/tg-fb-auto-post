# Server Deployment Notes

## Target Server

- Host: `161.118.204.251`
- User: `ubuntu`
- SSH key: `C:\Users\Shihab\Downloads\ssh-key-2026-03-17.key`

## Server-Only Policy

- Bot runtime runs on the server
- Oracle wallet and runtime secrets stay on the server
- Redis runs on the server
- Logs and persistent volumes stay on the server
- Any test execution happens on the server

## Planned Server Layout

- `/opt/everithing_manager/app`
- `/opt/everithing_manager/config`
- `/opt/everithing_manager/logs`
- `/opt/everithing_manager/backups`
- `/opt/everithing_manager/compose`

## Planned Runtime Services

- `bot`
- `redis`
- optional `worker`

Oracle remains external and is accessed through a dedicated bot schema.

## Oracle Assets To Place On Server

- Wallet zip file
- Extracted wallet directory
- Server-side environment variables

## Environment Variables

- `BOT_TOKEN`
- `BOT_OWNER_ID`
- `ORACLE_USER`
- `ORACLE_PASSWORD`
- `ORACLE_DSN`
- `ORACLE_WALLET_DIR`
- `REDIS_URL`
- `APP_ENV`
