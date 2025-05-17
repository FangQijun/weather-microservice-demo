"""
Script to load gridpoints data from TSV files into TimescaleDB.
"""
import os
import sys
import argparse
from typing import List, Dict, Any, Optional
import time
from pathlib import Path

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)
from src.database.timescale_db_connection import get_db_cursor, test_connection
from src.database.create_schema_gridpoints import initialize_schema
from app.utils.process_gridpoints import get_most_recent_file, parse_tsv_file, validate_gridpoint_row
from app.utils.log_config import setup_logging


logger = setup_logging(
    logs_dir="logs",
    logs_sub_dir="load",
    module_name=os.path.splitext(os.path.basename(__file__))[0]
)


def insert_gridpoints(gridpoints: List[Dict[str, Any]], batch_size: int = 1000) -> bool:
    """
    Insert gridpoints data into the database in batches.
    
    Args:
        gridpoints (List[Dict[str, Any]]): List of validated gridpoint dictionaries
        batch_size (int): Number of records to insert in each batch
        
    Returns:
        bool: True if successful
    """
    total_records = len(gridpoints)
    successful_inserts = 0
    
    # SQL for inserting a gridpoint
    insert_sql = """
    INSERT INTO gridpoints (
        api_call_id, centroid_lon, centroid_lat, grid_id, grid_x, grid_y,
        forecast_url, forecast_hourly_url, forecast_office_url, forecast_grid_data_url,
        observation_stations_url, forecast_zone_url, time_zone, radar_station
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    """
    
    try:
        # Process in batches
        for i in range(0, total_records, batch_size):
            batch = gridpoints[i:i+batch_size]
            
            with get_db_cursor(commit=True) as cursor:
                # Prepare batch data for executemany
                batch_data = [
                    (
                        gp['api_call_id'], 
                        gp['centroid_lon'], 
                        gp['centroid_lat'],
                        gp['grid_id'], 
                        gp['grid_x'], 
                        gp['grid_y'],
                        gp['forecast_url'], 
                        gp['forecast_hourly_url'], 
                        gp['forecast_office_url'],
                        gp['forecast_grid_data_url'], 
                        gp['observation_stations_url'], 
                        gp['forecast_zone_url'],
                        gp['time_zone'], 
                        gp['radar_station']
                    )
                    for gp in batch
                ]
                
                cursor.executemany(insert_sql, batch_data)
                
                # Update counters
                successful_inserts += len(batch)
                logger.info(f"Inserted batch {i//batch_size + 1}: {len(batch)} records. Progress: {successful_inserts}/{total_records}")
        
        logger.info(f"Successfully inserted {successful_inserts} gridpoints into the database")
        return True
    
    except Exception as e:
        logger.error(f"Error inserting gridpoints: {str(e)}")
        return False


def load_gridpoints_from_tsv(file_path: str, num_rows: Optional[int] = None, batch_size: int = 1000, mode: str = 'o') -> bool:
    """
    Main function to load gridpoints from a TSV file into the database.
    
    Args:
        file_path (str): Path to the TSV file
        batch_size (int): Number of records to insert in each batch
        
    Returns:
        bool: True if successful
    """
    start_time = time.time()
    logger.info(f"Starting to load gridpoints from {file_path}")
    
    try:
        # Test database connection
        if not test_connection():
            logger.error("Database connection failed. Aborting.")
            return False
        
        # Initialize schema if needed
        if not initialize_schema():
            logger.error("Schema initialization failed. Aborting.")
            return False
        
        # Parse the TSV file
        try:
            raw_data = parse_tsv_file(file_path, num_rows=num_rows)
            logger.info(f"Parsed {len(raw_data)} records from {file_path}")
        except Exception as e:
            logger.error(f"Error parsing TSV file: {str(e)}")
            return False
        
        # Validate and clean the data
        valid_gridpoints = []
        for row in raw_data:
            validated_row = validate_gridpoint_row(row)
            if validated_row:
                valid_gridpoints.append(validated_row)
        
        logger.info(f"Validated {len(valid_gridpoints)} of {len(raw_data)} records")
        
        if not valid_gridpoints:
            logger.error("No valid gridpoints found in the file. Aborting.")
            return False
        
        # Check if the mode is 'o' (overwrite) or 'a' (append)
        if mode == 'o':
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("TRUNCATE TABLE gridpoints;")
                logger.info("Gridpoints table truncated for overwrite mode")
        
        # Insert the validated data
        success = insert_gridpoints(valid_gridpoints, batch_size)
        
        end_time = time.time()
        logger.info(f"Gridpoints loading completed in {end_time - start_time:.2f} seconds")
        
        return success
    
    except Exception as e:
        logger.error(f"Error loading gridpoints: {str(e)}")
        return False


def main():
    """
    Main entry point for the script.
    """
    parser = argparse.ArgumentParser(description='Load gridpoints data from TSV into TimescaleDB')
    parser.add_argument('--num_rows', type=int, default=None, help='Number of rows to read from the file.')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for database inserts')
    parser.add_argument('--mode', type=str, default='o', choices=['o', 'a'], help='Mode of operation: "o" for overwrite, "a" for append')
    args = parser.parse_args()
    file_path = None
    
    logger.info("Attempting to automatically find the most recent gridpoints TSV file")
    file_path = get_most_recent_file(sub_folder="gridpoints_file")
    if not file_path:
        logger.error("No suitable TSV files found. Please specify a file path.")
        return 1
    logger.info(f"Found most recent file: {file_path}")
    
    if not os.path.isfile(file_path):
        logger.error(f"File does not exist: {file_path}")
        return 1
    
    # Load the data
    success = load_gridpoints_from_tsv(
        file_path=file_path,
        num_rows=args.num_rows,
        batch_size=args.batch_size,
        mode=args.mode
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())