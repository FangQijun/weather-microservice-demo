import os
import pandas as pd
import geopandas as gpd
import pygris  # This package provides easy access to Census TIGER/Line data
from log_config import setup_logging


logger = setup_logging(logs_dir="logs", logs_sub_dir="extract", module_name="grid_utils")
pd.set_option('display.max_columns', None)


def create_us_grid(shapefile_path=None, output_path=None):
    """
    Create a 2.5km x 2.5km grid covering the contiguous United States.
    
    Parameters:
    -----------
    shapefile_path : str, optional
        Path to save the U.S. States as a Shapefile
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
    us_states = us_states.sort_values(by="GEOID")
    logger.info(f"Loaded official US boundary data from Census Bureau!")
    logger.info(f"Returned US states data type: {type(us_states)}.")
    logger.info("Returned US states data summary: \n{}".format(us_states.head(6)))
    rows, columns = us_states.shape
    list_states = sorted(us_states['STUSPS'].unique())
    logger.info(f"Before filtering, # of Rows: {rows}, # of Columns: {columns}, including states: {list_states}")

    try:
        us_states.to_file(shapefile_path)
        logger.info(f"Saved US states data to file {shapefile_path}!")
    except Exception as e:
        logger.error(f"Error saving shapefile: {e}")
        return None
    
    # Filter to contiguous 48 states + DC (excluding Alaska, Hawaii, and territories)
    contiguous_fips = [str(i).zfill(2) for i in range(1, 57)
                     if i not in [2, 15, 60, 66, 69, 72, 78]]  # Exclude AK, HI, territories
    contiguous_us = us_states[us_states['GEOID'].isin(contiguous_fips)]
    rows, columns = contiguous_us.shape
    list_states = sorted(contiguous_us['STUSPS'].unique())
    logger.info(f"After filtering, # of Rows: {rows}, # of Columns: {columns}, including states: {list_states}")

    return None