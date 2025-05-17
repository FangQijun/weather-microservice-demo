import os
import sys
import psycopg2

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)
from app.utils.log_config import setup_logging


logger = setup_logging(
    logs_dir="logs",
    logs_sub_dir="extract",
    module_name="test_ts_db_conn"
)


def main():
    conn = psycopg2.connect("dbname=weather_db user=qijunfang")
    cur = conn.cursor()
    cur.execute("SELECT now()")
    logger.info(cur.fetchone())
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()