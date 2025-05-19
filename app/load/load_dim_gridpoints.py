"""
Script to load dim gridpoints data from TSV files into TimescaleDB.
"""
import os
import sys
import argparse
import time
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)
from src.database.timescale_db_connection import get_db_cursor, test_connection
from src.database.define_schemas import initialize_dim_gridpoints_schema
from app.utils.process_gridpoints import get_most_recent_file, parse_tsv_file
from app.utils.log_config import setup_logging


logger = setup_logging(
    logs_dir="logs",
    logs_sub_dir="load",
    module_name=os.path.splitext(os.path.basename(__file__))[0]
)


def insert_dim_gridpoints(dim_gridpoints: List[Dict[str, Any]]) -> bool:
    """
    Helper function to insert unique gridpoints data into the database.
    
    Args:
        dim_gridpoints (List[Dict[str, Any]]): List of validated gridpoint dictionaries
        batch_size (int): Number of records to insert in each batch
        
    Returns:
        bool: True if successful
    """
    total_records = len(dim_gridpoints)
    successful_inserts = 0
    
    # SQL for inserting a gridpoint
    INSERT_VALUES_TO_TABLE = """
    INSERT INTO dim_gridpoints (
        id, grid_id, grid_x, grid_y, elevation,
        geometry_type, geometry_coordinates,
        polygon, polygon_srid,
        polygon_centroid, polygon_centroid_srid, polygon_centroid_lon, polygon_centroid_lat
    ) VALUES (
        %s, %s, %s, %s, %s, 
        %s, %s, %s, %s, %s, 
        %s, %s, %s
    )
    """

    ADD_GEOGRAPHY_AND_GEOMETRY_COLUMNS = """
    UPDATE dim_gridpoints 
    SET polygon = ST_GeomFromText(geometry_coordinates)::geography,
        polygon_srid = ST_SetSRID(ST_GeomFromText(geometry_coordinates), 4326)::geography,
        polygon_centroid = ST_Centroid(ST_GeomFromText(geometry_coordinates))::geography,
        polygon_centroid_srid = ST_SetSRID(ST_Centroid(ST_GeomFromText(geometry_coordinates)), 4326)::geography,
        polygon_centroid_lon = ST_X(ST_Centroid(ST_GeomFromText(geometry_coordinates))::geometry),
        polygon_centroid_lat = ST_Y(ST_Centroid(ST_GeomFromText(geometry_coordinates))::geometry)
    """
    
    try:
        with get_db_cursor(commit=True) as cursor:
            # Prepare data for executemany
            batch_data = [
                (
                    gp.get('id'),
                    gp.get('grid_id'),
                    gp.get('grid_x'),
                    gp.get('grid_y'),
                    gp.get('elevation'),
                    gp.get('geometry_type'),
                    gp.get('geometry_coordinates'),
                    None,  # polygon - will be populated by the UPDATE statement
                    None,  # polygon_srid - will be populated by the UPDATE statement
                    None,  # polygon_centroid - will be populated by the UPDATE statement
                    None,  # polygon_centroid_srid - will be populated by the UPDATE statement
                    None,  # polygon_centroid_lon - will be populated by the UPDATE statement
                    None   # polygon_centroid_lat - will be populated by the UPDATE statement
                )
                for gp in dim_gridpoints
            ]
            
            cursor.executemany(INSERT_VALUES_TO_TABLE, batch_data)
        
            # Add geography and geometry columns
            cursor.execute(ADD_GEOGRAPHY_AND_GEOMETRY_COLUMNS)
            
            logger.info(f"Successfully inserted {total_records} dim_gridpoints into the database")
            return True
    
    except Exception as e:
        logger.error(f"Error inserting dim_gridpoints: {str(e)}")
        return False


def ingest_unique_gridpoints_from_tsv(file_path: str, mode: str = 'o', verbose: bool = False) -> bool:
    """
    Main function to ingest unique gridpoints from a TSV file into the database.
    
    Args:
        file_path (str): Path to the gridpoints dim data
        batch_size (int): Number of records to insert in each batch
        
    Returns:
        bool: True if successful
    """
    start_time = time.time()
    logger.info(f"Starting to read unique gridpoints data from {file_path}")

    try:
        # Test database connection
        if not test_connection():
            logger.error("Database connection failed. Aborting.")
            return False
        
        # Initialize schema if needed
        if not initialize_dim_gridpoints_schema():
            logger.error("Schema initialization failed. Aborting.")
            return False
        
        # Parse the TSV file
        try:
            raw_data = parse_tsv_file(file_path)
            logger.info(f"Parsed {len(raw_data)} records from {file_path}")
        except Exception as e:
            logger.error(f"Error parsing TSV file: {str(e)}")
            return False
        
        # Check if the mode is 'o' (overwrite) or 'a' (append)
        if mode == 'o':
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("TRUNCATE TABLE dim_gridpoints;")
                logger.info("Dim Gridpoints table truncated for overwrite mode")
        
        # Insert the validated data
        success = insert_dim_gridpoints(raw_data)
        
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
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    
    logger.info("Attempting to automatically find the most recent gridpoints TSV file")
    try:
        file_path = get_most_recent_file(
            sub_folder="gridpoints_file",
            prefix = "gridpoint_polygons_contiguous_us_",
            extension = '.tsv'
        )
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1

    success = ingest_unique_gridpoints_from_tsv(
        file_path=file_path,
        verbose=args.verbose
    )
    if not success:
        logger.error("Failed to ingest unique gridpoints from the TSV file.")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
