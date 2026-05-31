from __future__ import annotations

import argparse
from pathlib import Path

import oracledb


REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if not ENV_FILE.exists():
        raise FileNotFoundError(f"Missing env file: {ENV_FILE}")
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def split_sql_statements(sql_text: str) -> list[str]:
    return [
        statement.strip()
        for statement in sql_text.split(";")
        if statement.strip() and statement.strip().upper() != "COMMIT"
    ]


def apply_sql(sql_path: Path) -> int:
    env = load_env()
    sql_text = sql_path.read_text(encoding="utf-8")
    statements = split_sql_statements(sql_text)
    connection = oracledb.connect(
        user=env["ORACLE_USER"],
        password=env["ORACLE_PASSWORD"],
        dsn=env["ORACLE_DSN"],
        config_dir=env.get("ORACLE_WALLET_DIR"),
        wallet_location=env.get("ORACLE_WALLET_DIR"),
        wallet_password=env.get("ORACLE_PASSWORD"),
    )
    applied = 0
    with connection:
        with connection.cursor() as cursor:
            for statement in statements:
                try:
                    cursor.execute(statement)
                    applied += 1
                    print("APPLIED")
                except Exception as exc:  # pragma: no cover - operational helper
                    message = str(exc)
                    if "ORA-01430" in message or "ORA-01442" in message or "already exists" in message.lower():
                        print("SKIPPED_EXISTING")
                        continue
                    raise
        connection.commit()
    return applied


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply an Oracle SQL file using project .env credentials.")
    parser.add_argument("sql_file", help="Relative or absolute path to the SQL file.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sql_path = Path(args.sql_file)
    if not sql_path.is_absolute():
        sql_path = (REPO_ROOT / sql_path).resolve()
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")
    applied = apply_sql(sql_path)
    print(f"DONE | applied={applied}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
