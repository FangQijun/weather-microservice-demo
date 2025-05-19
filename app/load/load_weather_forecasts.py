"""
Script to load weather forecast data from TSV files into TimescaleDB.
"""
import os
import sys
import argparse
import pandas as pd
from typing import List, Dict, Any, Optional
import time
from pathlib import Path

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)
from src.database.timescale_db_connection import get_db_cursor, test_connection
from src.database.define_schemas import initialize_forecast_schema
from app.utils.log_config import setup_logging


logger = setup_logging(
    logs_dir="logs",
    logs_sub_dir="load",
    module_name=os.path.splitext(os.path.basename(__file__))[0]
)


def load_forecast_from_tsv(file_path: str, is_hourly: bool, user_id: str = None, 
                           latitude: float = None, longitude: float = None,
                           verbose: bool = False) -> bool:
    """
    Load forecast data from TSV file into the database.
    
    Args:
        file_path (str): Path to the TSV file
        is_hourly (bool): Whether this is hourly forecast data
        user_id (str, optional): User ID to filter by
        latitude (float, optional): Latitude to filter by
        longitude (float, optional): Longitude to filter by
        verbose (bool): Whether to log detailed information
        
    Returns:
        bool: True if successful
    """
    table_name = "hourly_forecasts" if is_hourly else "daily_forecasts"
    forecast_type = "hourly" if is_hourly else "daily"
    
    if not os.path.exists(file_path):
        logger.error(f"TSV file not found: {file_path}")
        return False
    
    logger.info(f"Loading {forecast_type} forecast data from {file_path}")
    
    try:
        # Read TSV file into pandas DataFrame
        df = pd.read_csv(file_path, sep='\t')
        
        if verbose:
            logger.info(f"Read {len(df)} records from {file_path}")
            logger.info(f"Columns: {', '.join(df.columns)}")
        
        # Filter by user_id and coordinates if provided
        if user_id is not None:
            df = df[df['user_id'] == user_id]
            if verbose:
                logger.info(f"Filtered to {len(df)} records with user_id = {user_id}")
                
        if latitude is not None and longitude is not None:
            # Apply some tolerance due to floating point precision
            tolerance = 0.0001
            df = df[(df['input_latitude'] >= latitude - tolerance) & 
                    (df['input_latitude'] <= latitude + tolerance) &
                    (df['input_longitude'] >= longitude - tolerance) & 
                    (df['input_longitude'] <= longitude + tolerance)]
            if verbose:
                logger.info(f"Filtered to {len(df)} records with latitude ≈ {latitude} and longitude ≈ {longitude}")
        
        if len(df) == 0:
            logger.warning(f"No records matching the filter criteria.")
            return True  # Not an error, just no matching data
            
        # Convert column names to match database schema (if needed)
        # This assumes the TSV file columns match the database schema
        
        # Insert data into the database
        with get_db_cursor(commit=True) as cursor:
            # First, check if data already exists to avoid duplicates
            if user_id is not None and latitude is not None and longitude is not None:
                cursor.execute(f"""
                    DELETE FROM {table_name}
                    WHERE user_id = %s
                    AND ABS(input_latitude - %s) < 0.0001
                    AND ABS(input_longitude - %s) < 0.0001
                """, (user_id, latitude, longitude))
                
                if cursor.rowcount > 0 and verbose:
                    logger.info(f"Deleted {cursor.rowcount} existing records for this user and location")
            
            # Prepare column names for SQL insertion
            columns = df.columns.tolist()
            placeholders = ', '.join(['%s'] * len(columns))
            column_str = ', '.join(columns)
            
            # Create the INSERT query
            insert_query = f"INSERT INTO {table_name} ({column_str}) VALUES ({placeholders})"
            
            # Convert DataFrame to list of tuples for executemany
            records = [tuple(row) for row in df.values]
            
            # Insert all records
            cursor.executemany(insert_query, records)
            
            if verbose:
                logger.info(f"Inserted {len(records)} records into {table_name}")
        
        logger.info(f"Successfully loaded {forecast_type} forecast data into the database")
        return True
        
    except Exception as e:
        logger.error(f"Error loading {forecast_type} forecast data: {str(e)}")
        return False


def load_weather_forecasts(user_id: str = None, latitude: float = None, longitude: float = None, 
                          verbose: bool = False) -> bool:
    """
    Main function to load both daily and hourly weather forecasts into the database.
    
    Args:
        user_id (str, optional): User ID to filter by
        latitude (float, optional): Latitude to filter by
        longitude (float, optional): Longitude to filter by
        verbose (bool): Whether to log detailed information
        
    Returns:
        bool: True if successful
    """
    start_time = time.time()
    if verbose:
        logger.info("Starting to load weather forecast data")
    
    # Define paths to TSV files
    daily_path = os.path.join(project_root, "data", "forecast_daily", "forecast_daily.tsv")
    hourly_path = os.path.join(project_root, "data", "forecast_hourly", "forecast_hourly.tsv")
    
    # Check if files exist
    if not os.path.exists(daily_path):
        logger.error(f"Daily forecast file not found: {daily_path}")
        return False
    if not os.path.exists(hourly_path):
        logger.error(f"Hourly forecast file not found: {hourly_path}")
        return False
    
    # Test database connection
    if not test_connection():
        logger.error("Database connection failed. Aborting.")
        return False
    
    # Initialize schema if needed
    if not initialize_forecast_schema():
        logger.error("Failed to create forecast tables. Aborting.")
        return False
    
    # Parse the TSV files
    if not load_forecast_from_tsv(daily_path, False, user_id, latitude, longitude, verbose):
        logger.error("Failed to load daily forecast data.")
        return False
    if not load_forecast_from_tsv(hourly_path, True, user_id, latitude, longitude, verbose):
        logger.error("Failed to load hourly forecast data.")
        return False
    
    end_time = time.time()
    logger.info(f"Weather forecast data loading completed in {end_time - start_time:.2f} seconds")
    
    return True


def main():
    """
    Main entry point for the script.
    """
    parser = argparse.ArgumentParser(description='Load weather forecast data from TSV into TimescaleDB')
    parser.add_argument('--user-id', type=str, help='User ID to filter by')
    parser.add_argument('--latitude', type=float, help='Latitude to filter by')
    parser.add_argument('--longitude', type=float, help='Longitude to filter by')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Load the data
    success = load_weather_forecasts(
        user_id=args.user_id,
        latitude=args.latitude,
        longitude=args.longitude,
        verbose=args.verbose
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
    # Example CLI command to run the script locally:
    # python app/load/load_weather_forecasts.py