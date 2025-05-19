"""
Script to transform weather forecast data in TimescaleDB with derived metrics.
"""
import os
import sys
import argparse
import time
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)
from src.database.timescale_db_connection import get_db_cursor, test_connection
from src.database.define_schemas import initialize_metric_schema
from app.utils.log_config import setup_logging


logger = setup_logging(
    logs_dir="logs",
    logs_sub_dir="transform",
    module_name=os.path.splitext(os.path.basename(__file__))[0]
)


def calculate_hourly_metrics(user_id: str, request_timestamp: str, verbose: bool = False) -> List[Dict[str, Any]]:
    """
    Calculate hourly metrics from forecasts_hourly table.
    
    Args:
        user_id (str): User ID to filter by
        request_timestamp (str): Request timestamp to filter by
        verbose (bool): Whether to log detailed information
        
    Returns:
        List[Dict[str, Any]]: List of dictionaries with calculated metrics for each hour
    """
    logger.info(f"Calculating hourly metrics for user {user_id} at timestamp {request_timestamp}")
    
    HOURLY_METRICS_QUERY = """
    SELECT
        user_id,
        request_timestamp,
        input_longitude,
        input_latitude,
        start_time,
        end_time,
        number,
        temperature,
        max_temperature_in_24hr_window,
        min_temperature_in_24hr_window,
        CASE
            WHEN max_temperature_in_24hr_window = min_temperature_in_24hr_window THEN 1
            ELSE 1.0 * (temperature - min_temperature_in_24hr_window) / (max_temperature_in_24hr_window - min_temperature_in_24hr_window)
        END AS temperature_ratio_in_24hr_window,
        wind_speed,
        wind_speed > avg_wind_speed_in_24hr_window AS wind_exceeds_daily_avg,
        grid_id,
        grid_x,
        grid_y,
        grid_geometry_coordinates,
        grid_polygon_centroid_lon,
        grid_polygon_centroid_lat,
        lat_distance_from_forecast,
        lon_distance_from_forecast,
        probability_precipitation::VARCHAR(3) || '%' AS probability_precipitation
    FROM (
        SELECT DISTINCT
            user_id,
            request_timestamp,
            input_longitude,
            input_latitude,
            start_time,
            end_time,
            number,
            temperature,
            MAX(temperature) OVER (
                PARTITION BY user_id, request_timestamp, input_longitude, input_latitude
                ORDER BY number
                ROWS BETWEEN CURRENT ROW AND 23 FOLLOWING
            ) AS max_temperature_in_24hr_window,
            MIN(temperature) OVER (
                PARTITION BY user_id, request_timestamp, input_longitude, input_latitude
                ORDER BY number
                ROWS BETWEEN CURRENT ROW AND 23 FOLLOWING
            ) AS min_temperature_in_24hr_window,
            wind_speed,
            AVG(wind_speed) OVER (
                PARTITION BY user_id, request_timestamp, input_longitude, input_latitude
                ORDER BY number
                ROWS BETWEEN CURRENT ROW AND 23 FOLLOWING
            ) AS avg_wind_speed_in_24hr_window,
            grid_id,
            grid_x,
            grid_y,
            grid_geometry_coordinates,
            grid_polygon_centroid_lon,
            grid_polygon_centroid_lat,
            ABS(grid_polygon_centroid_lon - input_longitude) AS lon_distance_from_forecast,
            ABS(grid_polygon_centroid_lat - input_latitude) AS lat_distance_from_forecast,
            probability_precipitation
        FROM (
            SELECT 
                hf.user_id,
                hf.request_timestamp,
                hf.input_longitude,
                hf.input_latitude,
                hf.start_time,
                hf.end_time,
                hf.number,
                hf.temperature,
                COALESCE(hf.wind_speed_low, 0) AS wind_speed_low,
                COALESCE(hf.wind_speed_high, 0) AS wind_speed_high,
                (COALESCE(hf.wind_speed_low, 0) + COALESCE(hf.wind_speed_high, 0)) / 2.0 AS wind_speed,
                dg.grid_id,
                dg.grid_x,
                dg.grid_y,
                dg.geometry_coordinates AS grid_geometry_coordinates,
                dg.polygon_centroid_lon AS grid_polygon_centroid_lon,
                dg.polygon_centroid_lat AS grid_polygon_centroid_lat,
                COALESCE(hf.probability_precipitation, 0) AS probability_precipitation
            FROM 
                hourly_forecasts AS hf
            LEFT JOIN
                dim_gridpoints AS dg
            ON
                hf.grid_id = dg.grid_id
                AND hf.grid_x = dg.grid_x
                AND hf.grid_y = dg.grid_y
            WHERE 
                hf.user_id = '{}'
                AND hf.request_timestamp = '{}'
        ) AS w
    ) AS u
    ORDER BY 1,2,3,4,5
    LIMIT 24;
    """
    # For testing: user_id = 'demo_user', request_timestamp = '2025-05-19 05:15:14.37935+00'
    
    try:
        with get_db_cursor() as cursor:
            logger.info(HOURLY_METRICS_QUERY.format(user_id, request_timestamp))
            cursor.execute(HOURLY_METRICS_QUERY.format(user_id, request_timestamp))
            # Suprisingly, both `request_timestamp = '2025-05-19T05:15:14.37935Z'`
            # ... and `request_timestamp = '2025-05-19 05:15:14.37935+00'` are allowed PostgreSQL syntax
            # ... to filter by exact `TIMESTAMPTZ` data type value.
            
            hourly_metrics = []
            for row in cursor.fetchall():
                # Convert row to dictionary
                columns = [desc[0] for desc in cursor.description]
                hourly_data = dict(zip(columns, row))
                hourly_metrics.append(hourly_data)
            
            if verbose:
                logger.info(f"Calculated hourly metrics for {len(hourly_metrics)} hours")
            
            return hourly_metrics
            
    except Exception as e:
        logger.error(f"Error calculating hourly metrics: {str(e)}")
        return []


def save_augmented_metrics(hourly_metrics: List[Dict[str, Any]], verbose: bool = False) -> bool:
    """
    Save calculated metrics to the augmented tables.
    
    Args:
        hourly_metrics (List[Dict[str, Any]]): Hourly metrics to save
        verbose (bool): Whether to log detailed information
        
    Returns:
        bool: True if successful
    """
    logger.info("Saving augmented metrics to database")
    
    try:
        with get_db_cursor(commit=True) as cursor:
            if hourly_metrics:
                df = pd.DataFrame(hourly_metrics)

                # Prepare column names for SQL insertion
                columns = df.columns.tolist()
                placeholders = ', '.join(['%s'] * len(columns))
                column_str = ', '.join(columns)
                
                # Create the INSERT query
                insert_query = f"INSERT INTO forecasts_hourly_metrics ({column_str}) VALUES ({placeholders})"

                # Convert DataFrame to list of tuples for executemany
                records = [tuple(row) for row in df.values]
                
                # Insert all records
                cursor.executemany(insert_query, records)
                
                if verbose:
                    logger.info(f"Inserted {len(hourly_metrics)} into table forecasts_hourly_metrics")
            
            return True
            
    except Exception as e:
        logger.error(f"Error saving augmented metrics: {str(e)}")
        return False


def transform_weather_forecasts(request_timestamp: str, user_id: str, latitude: float = None, longitude: float = None, verbose: bool = False) -> bool:
    """
    Main function to transform weather forecasts with derived metrics.
    
    Args:
        request_timestamp (str): Request timestamp to filter by
        user_id (str): User ID to filter by
        latitude (float, optional): Latitude for reference
        longitude (float, optional): Longitude for reference
        verbose (bool): Whether to log detailed information
        
    Returns:
        bool: True if successful
    """
    start_time = time.time()
    logger.info(f"Starting to transform weather forecasts for user {user_id} at timestamp {request_timestamp}")
    
    # Test database connection
    if not test_connection():
        logger.error("Database connection failed. Aborting.")
        return False
    
    # Create tables if they don't exist
    if not initialize_metric_schema():
        logger.error("Failed to create augmented tables. Aborting.")
        return False
    
    # Calculate hourly metrics
    hourly_metrics = calculate_hourly_metrics(user_id, request_timestamp, verbose)
    if not hourly_metrics:
        logger.warning("No hourly metrics calculated.")
    
    # Save metrics to database
    if not save_augmented_metrics(hourly_metrics, verbose):
        logger.error("Failed to save augmented metrics.")
        return False
    
    end_time = time.time()
    logger.info(f"Weather forecast transformation completed in {end_time - start_time:.2f} seconds")
    
    return True


def main():
    """
    Main entry point for the script.
    """
    parser = argparse.ArgumentParser(description='Transform weather forecast data in TimescaleDB with derived metrics')
    parser.add_argument('--request-timestamp', type=str, required=True, help='Request timestamp to filter by')
    parser.add_argument('--user-id', type=str, required=True, help='User ID to filter by')
    parser.add_argument('--latitude', type=float, help='Latitude for reference')
    parser.add_argument('--longitude', type=float, help='Longitude for reference')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Transform the data
    success = transform_weather_forecasts(
        request_timestamp=args.request_timestamp,
        user_id=args.user_id,
        latitude=args.latitude,
        longitude=args.longitude,
        verbose=args.verbose
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())