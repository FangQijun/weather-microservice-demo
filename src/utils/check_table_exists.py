"""
Check if a certain table exists in TimescaleDB/PostgreSQL.
"""
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)
from app.utils.log_config import setup_logging
from src.database.timescale_db_connection import get_db_cursor


logger = setup_logging(
    logs_dir="logs",
    logs_sub_dir="database",
    module_name=os.path.splitext(os.path.basename(__file__))[0]
)


def check_table_exists(table_name: str) -> bool:
    """
    Check if a table exists in the database.
    
    Args:
        table_name (str): Name of the table to check
        
    Returns:
        bool: True if the table exists, False otherwise
    """
    try:
        with get_db_cursor(commit=False) as cursor:
            LIST_TABLE_BY_NAME = """
            SELECT table_schema, table_name 
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
            AND table_schema = 'public'
            AND table_name = '{}';
            """.format(table_name)
            
            cursor.execute(LIST_TABLE_BY_NAME)
            result = cursor.fetchone()
            exists = result is not None
            if exists:
                logger.info(f"Table {table_name} exists.")
            else:
                logger.warning(f"Table {table_name} does NOT exist.")
        return exists
    except Exception as e:
        logger.warning(f"List table query failed: {str(e)}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: Table name not provided")
        print("Usage: python src/utils/check_table_exists.py <table_name>")
        sys.exit(1)
    
    table_name = sys.argv[1]
    result = check_table_exists(table_name)
    logger.info(f"Table '{table_name}' exists: {result}")