from __future__ import annotations

import os
import sys

import oracledb


def main() -> int:
    statements = [statement.strip() for statement in sys.argv[1:] if statement.strip()]
    if not statements:
        raise SystemExit("Provide at least one SQL statement.")

    connection = oracledb.connect(
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        dsn=os.environ["ORACLE_DSN"],
        config_dir=os.environ.get("ORACLE_WALLET_DIR"),
        wallet_location=os.environ.get("ORACLE_WALLET_DIR"),
        wallet_password=os.environ.get("ORACLE_PASSWORD"),
    )
    with connection:
        with connection.cursor() as cursor:
            for statement in statements:
                try:
                    cursor.execute(statement)
                    print("APPLIED")
                except Exception as exc:  # pragma: no cover - operational helper
                    message = str(exc)
                    if "ORA-01430" in message or "already exists" in message.lower():
                        print("SKIPPED_EXISTING")
                        continue
                    raise
        connection.commit()
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
