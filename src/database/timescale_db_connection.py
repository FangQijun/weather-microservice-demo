"""
Database connection module for the Weather DB application.
Handles connections to TimescaleDB/PostgreSQL.
"""
import os
import sys
import psycopg2
from dotenv import load_dotenv
from typing import Optional, Generator
from psycopg2.extensions import connection
from contextlib import contextmanager

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)
from app.utils.log_config import setup_logging


logger = setup_logging(
    logs_dir="logs",
    logs_sub_dir="database",
    module_name=os.path.splitext(os.path.basename(__file__))[0]
)


# Database configuration - can be moved to environment variables or config file
load_dotenv()
DB_CONFIG = {
    "dbname": os.environ.get("DB_NAME"),
    "user": os.environ.get("DB_USER"),
    "password": os.environ.get("DB_PASSWORD", ""),  # Default empty for local development
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432")
}


def get_connection() -> connection:
    """
    Create and return a connection to the PostgreSQL/TimescaleDB database.
    
    Returns:
        connection: A PostgreSQL database connection
    
    Raises:
        Exception: If connection fails
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info(f"Successfully connected to database {DB_CONFIG['dbname']}")
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        raise


@contextmanager
def get_db_cursor(commit: bool = False) -> Generator:
    """
    Context manager for database operations.
    
    Args:
        commit (bool): Whether to commit the transaction
        
    Yields:
        cursor: A database cursor for executing queries
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        yield cursor
        if commit:
            conn.commit()
            logger.debug("Transaction committed")
    except Exception as e:
        if conn and commit:
            conn.rollback()
            logger.warning("Transaction rolled back due to error")
        logger.error(f"Database operation failed: {str(e)}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def test_connection() -> bool:
    """
    Test the database connection.
    
    Returns:
        bool: True if connection successful
    """
    try:
        with get_db_cursor() as cursor:
            # Check which database we're connected to
            cursor.execute("SELECT current_database();")
            db_name = cursor.fetchone()[0]
            logger.info(f"Connected to database: {db_name}")
            
            # Check PostgreSQL version
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            logger.info(f"PostgreSQL version: {version[0]}")
            
            # Show all extensions
            cursor.execute("SELECT extname, extversion FROM pg_extension;")
            extensions = cursor.fetchall()
            logger.info(f"Available extensions: {', '.join([ext[0] for ext in extensions])}")
            
            # Check specifically for TimescaleDB extension
            cursor.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';")
            timescale = cursor.fetchone()
            if timescale:
                logger.info(f"TimescaleDB extension found: version {timescale[1]}")
            else:
                logger.warning("TimescaleDB extension not found in current database!")
                logger.info("Attempting to create TimescaleDB extension...")
                try:
                    with get_db_cursor(commit=True) as create_cursor:
                        create_cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
                    logger.info("Successfully created TimescaleDB extension")
                except Exception as ext_err:
                    logger.error(f"Failed to create TimescaleDB extension: {str(ext_err)}")
                
        return True
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        return False


if __name__ == "__main__":
    test_connection()