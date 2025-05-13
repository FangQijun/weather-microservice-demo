import os
import logging
import geopandas as gpd
import pygris  # This package provides easy access to Census TIGER/Line data

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
    # Load US states boundaries (most recent version) using tigris
    print("Loading official US boundary data from Census Bureau...")
    us_states = pygris.states(year=2024)  # Returns a GeoDataFrame
    us_states.to_file(shapefile_path)
    print(type(us_states))

    return None