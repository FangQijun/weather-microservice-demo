"""
Database schema definitions for the Weather DB application.
Defines tables, hypertables, and indexes.
"""
import os
import sys
import logging

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)
from app.utils.log_config import setup_logging
from src.database.timescale_db_connection import get_db_cursor
from src.utils.check_table_exists import check_table_exists


logger = setup_logging(
    logs_dir="logs",
    logs_sub_dir="database",
    module_name=os.path.splitext(os.path.basename(__file__))[0]
)

# SQL for creating the gridpoints table
CREATE_GRIDPOINTS_TABLE = """
CREATE TABLE IF NOT EXISTS gridpoints (
    id SERIAL PRIMARY KEY,
    api_call_id TEXT,
    centroid_lon DOUBLE PRECISION NOT NULL,
    centroid_lat DOUBLE PRECISION NOT NULL,
    grid_id TEXT NOT NULL,
    grid_x INTEGER NOT NULL,
    grid_y INTEGER NOT NULL,
    forecast_url TEXT,
    forecast_hourly_url TEXT,
    forecast_office_url TEXT,
    forecast_grid_data_url TEXT,
    observation_stations_url TEXT,
    forecast_zone_url TEXT,
    time_zone TEXT,
    radar_station TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

# Add PostGIS extension and geography column
CREATE_POSTGIS_EXTENSION = "CREATE EXTENSION IF NOT EXISTS postgis;"
ADD_GEOGRAPHY_COLUMN = """
ALTER TABLE gridpoints 
ADD COLUMN IF NOT EXISTS geog GEOGRAPHY(POINT);
UPDATE gridpoints SET geog = ST_SetSRID(ST_MakePoint(centroid_lon, centroid_lat), 4326)::geography
WHERE geog IS NULL;
"""

# Index for the common query patterns
CREATE_GRIDPOINTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_gridpoints_grid_id ON gridpoints (grid_id);",
    "CREATE INDEX IF NOT EXISTS idx_gridpoints_grid_xy ON gridpoints (grid_id, grid_x, grid_y);",
    "CREATE INDEX IF NOT EXISTS idx_gridpoints_coords ON gridpoints (centroid_lat, centroid_lon);"
    "CREATE INDEX IF NOT EXISTS idx_gridpoints_geog ON gridpoints USING GIST(geog);"
]


def initialize_schema():
    """
    Initialize the database schema for the Weather DB.
    Creates tables and indexes if they don't exist.
    """
    try:
        with get_db_cursor(commit=True) as cursor:
            # Create gridpoints table
            cursor.execute(CREATE_GRIDPOINTS_TABLE)
            logger.info("Gridpoints table created or already exists")
            
            # You can enable these if you decide to use PostGIS
            cursor.execute(CREATE_POSTGIS_EXTENSION)
            cursor.execute(ADD_GEOGRAPHY_COLUMN)
            logger.info("PostGIS extension and geography column added")
            
            # Create indexes
            for index_sql in CREATE_GRIDPOINTS_INDEXES:
                cursor.execute(index_sql)
            logger.info("Gridpoints indexes created or already exist")
        if check_table_exists(table_name="gridpoints"):
            logger.info("Gridpoints table exists and is ready for use")
            logger.info("Schema initialization completed successfully")
        else:
            logger.warning("Gridpoints table does NOT exist after initialization")
            return False
        return True
    except Exception as e:
        logger.error(f"Schema initialization failed: {str(e)}")
        return False


def create_hypertable():
    """
    Convert regular tables to TimescaleDB hypertables for tables that have time-series data.
    """
    # Gridpoints table is a reference table rather than a hypertable
    pass


if __name__ == "__main__":
    initialize_schema()