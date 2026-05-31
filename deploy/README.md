# Deploy Notes

## Intended Flow

1. Sync this project to the Ubuntu server.
2. Place `.env` on the server.
3. Upload and extract the Oracle wallet on the server.
4. Build and start the compose stack on the server.

## Expected Server Paths

- `/opt/everithing_manager/app`
- `/opt/everithing_manager/config/oracle-wallet`
- `/opt/everithing_manager/logs`

## First Runtime Goal

Bring up:

- bot container
- redis container

Oracle remains an external service connection.
