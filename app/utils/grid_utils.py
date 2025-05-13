import os
import geopandas as gpd
import pygris  # This package provides easy access to Census TIGER/Line data
from log_config import setup_logging


logger = setup_logging(logs_dir="logs", logs_sub_dir="extract", module_name="grid_utils")


def create_us_grid(shapefile_path=None, output_path=None):
    """
    Create a 2.5km x 2.5km grid covering the contiguous United States.
    
    Parameters:
    -----------
    output_path : str, optional
        Path to save the grid as a GeoPackage file
        
    Returns:
    --------
    gpd.GeoDataFrame
        GeoDataFrame containing the grid cells
    """
    # Load US states boundaries (most recent version) using pygris
    logger.info(f"Loading official US boundary data from Census Bureau...")
    us_states = pygris.states(year=2024)  # Returns a GeoDataFrame
    logger.info(f"Loaded official US boundary data from Census Bureau!")
    logger.info(f"Returned US states data type: {type(us_states)}.")

    try:
        us_states.to_file(shapefile_path)
        logger.info(f"Saved US states data to file {shapefile_path}!")
    except Exception as e:
        logger.error(f"Error saving shapefile: {e}")
        return None

    return None