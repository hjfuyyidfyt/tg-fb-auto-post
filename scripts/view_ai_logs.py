import os
import sys
import oracledb

def main():
    connection = oracledb.connect(
        user=os.environ.get("ORACLE_USER", "EVERYTHING_MANAGER_APP"),
        password=os.environ.get("ORACLE_PASSWORD", "Shoaib@12345"),
        dsn=os.environ.get("ORACLE_DSN", "peb11wp11w4qg69w_tp"),
        config_dir="/opt/everithing_manager/config/oracle-wallet",
        wallet_location="/opt/everithing_manager/config/oracle-wallet",
        wallet_password=os.environ.get("ORACLE_PASSWORD", "Shoaib@12345"),
    )
    with connection:
        with connection.cursor() as cursor:
            # Query last 10 log entries
            cursor.execute("""
                SELECT ID, ACTION_TYPE, ACTION_DETAILS, CREATED_AT 
                FROM EM_AI_LOGS 
                ORDER BY CREATED_AT DESC
            """)
            rows = cursor.fetchmany(10)
            print("--- EM_AI_LOGS ---")
            for r in rows:
                print(f"ID: {r[0]} | Action: {r[1]} | Time: {r[3]}")
                print(f"Details: {r[2]}")
                print("-" * 50)

if __name__ == "__main__":
    main()
