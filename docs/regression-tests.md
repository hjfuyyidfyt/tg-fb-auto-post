# Regression Tests

## Current Scope

The lightweight regression suite focuses on high-value logic that is easy to break during feature work:

- schedule parsing and recurrence behavior
- managed bot action input and preset normalization
- automation timing validation for cooldown and quiet hours
- automation trigger normalization and placeholder rendering
- dashboard-safe redirect and next-url helpers

## How To Run

From the project root:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Current Files

- `tests/test_schedule_service.py`
- `tests/test_bots_service.py`
- `tests/test_web_validation.py`
- `tests/test_automation_utils.py`
- `tests/test_web_safe_helpers.py`

## Notes

- These tests are intentionally dependency-light and do not require Oracle, Redis, or live Telegram access.
- They complement the server-side reliability checks instead of replacing them.
