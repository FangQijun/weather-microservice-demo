"""
Database schema definitions for the Weather DB application.
Defines tables, hypertables, and indexes.
"""
import os
import sys

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
    centroid_point GEOMETRY(POINT, 4326),
    centroid_srid GEOMETRY,
    geog GEOGRAPHY(POINT),
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

# Index for the common query patterns
CREATE_GRIDPOINTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_gridpoints_grid_id ON gridpoints (grid_id);",
    "CREATE INDEX IF NOT EXISTS idx_gridpoints_grid_xy ON gridpoints (grid_id, grid_x, grid_y);",
    "CREATE INDEX IF NOT EXISTS idx_gridpoints_coords ON gridpoints (centroid_lat, centroid_lon);",
    "CREATE INDEX IF NOT EXISTS idx_gridpoints_geog ON gridpoints USING GIST(geog);",
    "CREATE INDEX IF NOT EXISTS idx_gridpoints_centroid_point ON gridpoints USING GIST(centroid_point);"
]


def initialize_gridpoints_schema():
    """
    Defines the column schema of `gridpoints` table. Creates tables and indexes if they don't exist.
    
    Returns:
        bool: True if successful
    """
    try:
        with get_db_cursor(commit=True) as cursor:
            # Enable PostGIS, then create gridpoints table
            cursor.execute(CREATE_POSTGIS_EXTENSION)
            logger.info("PostGIS extension and geography column added")

            # Create gridpoints table
            cursor.execute(CREATE_GRIDPOINTS_TABLE)
            logger.info("Gridpoints table created or already exists")
            
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


# SQL for creating the daily and hourly forecasts tables
CREATE_DAILY_FORECASTS_TABLE = """
CREATE TABLE IF NOT EXISTS daily_forecasts (
    id BIGSERIAL,
    request_timestamp TIMESTAMPTZ NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    input_longitude FLOAT NOT NULL,
    input_latitude FLOAT NOT NULL,
    grid_id VARCHAR(10) NOT NULL,
    grid_x INTEGER NOT NULL,
    grid_y INTEGER NOT NULL,
    is_hourly BOOLEAN NOT NULL DEFAULT FALSE,
    generated_at TIMESTAMPTZ NOT NULL,
    update_time TIMESTAMPTZ NOT NULL,
    valid_times VARCHAR(100),
    number INTEGER,
    name VARCHAR(50),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    is_daytime BOOLEAN,
    temperature INTEGER,
    temperature_trend VARCHAR(50),
    probability_precipitation FLOAT,
    dew_point FLOAT,
    relative_humidity FLOAT,
    wind_speed_low INTEGER,
    wind_speed_high INTEGER,
    wind_direction VARCHAR(10),
    short_forecast TEXT,
    detailed_forecast TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, request_timestamp, input_longitude, input_latitude, start_time)
);
"""
CREATE_HOURLY_FORECASTS_TABLE = """
CREATE TABLE IF NOT EXISTS hourly_forecasts (
    id BIGSERIAL,
    request_timestamp TIMESTAMPTZ NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    input_longitude FLOAT NOT NULL,
    input_latitude FLOAT NOT NULL,
    grid_id VARCHAR(10) NOT NULL,
    grid_x INTEGER NOT NULL,
    grid_y INTEGER NOT NULL,
    is_hourly BOOLEAN NOT NULL DEFAULT TRUE,
    generated_at TIMESTAMPTZ NOT NULL,
    update_time TIMESTAMPTZ NOT NULL,
    valid_times VARCHAR(100),
    number INTEGER,
    name VARCHAR(50),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    is_daytime BOOLEAN,
    temperature INTEGER,
    temperature_trend VARCHAR(50),
    probability_precipitation FLOAT,
    dew_point FLOAT,
    relative_humidity FLOAT,
    wind_speed_low INTEGER,
    wind_speed_high INTEGER,
    wind_direction VARCHAR(10),
    short_forecast TEXT,
    detailed_forecast TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, request_timestamp, input_longitude, input_latitude, start_time)
);
"""

# SQL for creating TimescaleDB hypertables that power real-time analytics on time-series and event data.
CREATE_DAILY_HYPERTABLE = """
SELECT create_hypertable('daily_forecasts', 'start_time', if_not_exists => TRUE);
"""
CREATE_HOURLY_HYPERTABLE = """
SELECT create_hypertable('hourly_forecasts', 'start_time', if_not_exists => TRUE);
"""

# Indexes for the daily and hourly forecasts tables
CREATE_DAILY_FORECASTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_daily_forecasts_user_id ON daily_forecasts(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_daily_forecasts_grid_id_x_y ON daily_forecasts(grid_id, grid_x, grid_y);"
]
CREATE_HOURLY_FORECASTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_hourly_forecasts_user_id ON hourly_forecasts(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_hourly_forecasts_grid_id_x_y ON hourly_forecasts(grid_id, grid_x, grid_y);"
]


def initialize_forecast_schema() -> bool:
    """
    Defines the column schema of `daily_forecasts` and `hourly_forecasts` tables. Creates tables and indexes if they don't exist.
    
    Returns:
        bool: True if successful
    """
    try:
        with get_db_cursor(commit=True) as cursor:
            # Create daily and hourly forecasts tables
            cursor.execute(CREATE_DAILY_FORECASTS_TABLE)
            logger.info("Daily forecasts table created or already exists")
            cursor.execute(CREATE_HOURLY_FORECASTS_TABLE)
            logger.info("Hourly forecasts table created or already exists")
            
            # Create hypertables
            cursor.execute(CREATE_DAILY_HYPERTABLE)
            logger.info("Daily forecasts hypertable created or already exists")
            cursor.execute(CREATE_HOURLY_HYPERTABLE)
            logger.info("Hourly forecasts hypertable created or already exists")
            
            # Create indexes for daily and hourly forecasts tables
            for index_sql in CREATE_DAILY_FORECASTS_INDEXES:
                cursor.execute(index_sql)
            logger.info("Daily forecasts indexes created or already exist")
            for index_sql in CREATE_HOURLY_FORECASTS_INDEXES:
                cursor.execute(index_sql)
            logger.info("Hourly forecasts indexes created or already exist")
        
        # Verify tables exist
        daily_exists = check_table_exists(table_name="daily_forecasts")
        hourly_exists = check_table_exists(table_name="hourly_forecasts")
        
        if daily_exists and hourly_exists:
            logger.info("Forecast tables exist and are ready for use")
            logger.info("Schema initialization completed successfully")
        else:
            missing_tables = []
            if not daily_exists:
                missing_tables.append("daily_forecasts")
            if not hourly_exists:
                missing_tables.append("hourly_forecasts")
            logger.warning(f"The following tables do NOT exist after initialization: {', '.join(missing_tables)}")
            return False
        return True
    except Exception as e:
        logger.error(f"Forecast schema initialization failed: {str(e)}")
        return False


def create_hypertable():
    """
    Convert regular tables to TimescaleDB hypertables for tables that have time-series data.
    """
    # Gridpoints table is a reference table rather than a hypertable
    pass


if __name__ == "__main__":
    initialize_gridpoints_schema()
    initialize_forecast_schema()
    # Example CLI command to run the script locally:
    # python src/database/define_schemas.py