# Maintenance Runbook

## Fast checks

- Unit tests:
  - `python -m unittest discover -s tests -v`
- Reliability only:
  - `python scripts/reliability_check.py`
- Full check:
  - `python scripts/full_check.py`

## What `full_check.py` does

- runs the current unit test suite
- runs the dashboard/bot reliability sweep
- exits non-zero if either step fails

## Practical note

After a dashboard or bot rebuild, the first reliability run can briefly fail during startup while containers and Nginx settle. If the first run shows `502` or local connection resets right after deploy, rerun once after a short wait before treating it as a real failure.

## Recommended post-deploy order

1. `sudo docker compose up -d --build`
2. `python scripts/reliability_check.py`
3. if the first run fails immediately after deploy, wait a few seconds and rerun
4. `python scripts/full_check.py` when you want both unit tests and service checks together
