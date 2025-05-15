import os
import numpy as np
import pandas as pd
import geopandas as gpd
import pygris  # This package provides easy access to Census TIGER/Line data
from shapely.geometry import Polygon
from log_config import setup_logging


logger = setup_logging(logs_dir="logs", logs_sub_dir="extract", module_name="grid_utils")
pd.set_option('display.max_columns', None)


def create_us_grid(shapefile_path=None, output_path=None, align_with_coords=False):
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

    if shapefile_path:
        os.makedirs(os.path.dirname(shapefile_path), exist_ok=True)  # Create directory if it doesn't exist
        try:
            us_states.to_file(shapefile_path)
            logger.info(f"Saved US states data to file {shapefile_path}!")
        except Exception as e:
            logger.warning(f"Error saving shapefile: {e}")  # Can still proceed without saving the shapefile
    
    # Filter to contiguous 48 states + DC (excluding Alaska, Hawaii, and territories)
    contiguous_fips = [str(i).zfill(2) for i in range(1, 57)
                     if i not in [2, 15, 60, 66, 69, 72, 78]]  # Exclude AK, HI, territories
    contiguous_us = us_states[us_states['GEOID'].isin(contiguous_fips)]
    rows, columns = contiguous_us.shape
    list_states = sorted(contiguous_us['STUSPS'].unique())
    logger.info(f"After filtering, # of Rows: {rows}, # of Columns: {columns}, including states: {list_states}")

    # Project to an equal-area projection suitable for the US (EPSG:5070 - NAD83 / Conus Albers)
    contiguous_us = contiguous_us.to_crs(epsg=5070)

    if align_with_coords:
        align_poly = Polygon(align_with_coords)  # Convert the alignment coordinates to a polygon
        align_gdf = gpd.GeoDataFrame([{'geometry': align_poly}], crs='EPSG:4326')  # Create a GeoDataFrame with the alignment polygon in WGS84 (EPSG:4326)
        align_gdf = align_gdf.to_crs(epsg=5070)  # Project to the same CRS as our grid
        align_bounds = align_gdf.iloc[0].geometry.bounds  # Get the bounds and orientation of the alignment polygon
        logger.info(f"Aligning grid with provided coordinates (projected bounds: {align_bounds})")
        minx, miny, maxx, maxy = align_bounds  # Extract parameters for grid creation
        # Calculate the bearing/rotation if needed
        # (This is a simplified approach - for precise rotation, additional calculations would be needed)
        # For now, we'll use the alignment polygon's extent, but keep the grid cells at 2.5km size
    else:
        minx, miny, maxx, maxy = contiguous_us.total_bounds  # Bounding box of the contiguous US
    
    cell_size = 2500
    
    # Calculate the number of cells in x and y direction
    logger.info(f"")
    nx, ny = int(np.ceil((maxx - minx) / cell_size)), int(np.ceil((maxy - miny) / cell_size))    
    logger.info(f"Creating {nx} x {ny} = {nx * ny} grids...")  # 1846 * 1162 = 2,145,052 grids in total

    grid_list = []
    grid_ids = []
    centroids = []
    m = 0
    for i in range(nx):
        for j in range(ny):
            # Grid boundaries
            x0 = minx + i * cell_size
            y0 = miny + j * cell_size
            x1 = minx + (i + 1) * cell_size
            y1 = miny + (j + 1) * cell_size
            
            # Grid polygon
            plgn = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
            ctrd = plgn.centroid
            grid_list.append(plgn)
            grid_ids.append(f"grid_{m}")
            centroids.append(ctrd)
            m += 1
    
    grids = gpd.GeoDataFrame(
        {
            'id': grid_ids,
            'geometry': grid_list,
            'centroid': centroids
        },
        crs=contiguous_us.crs
    )
    
    # Filter to include only cells that intersect with the contiguous US
    logger.info(f"")
    logger.info(f"Filtering out grids that don't overlap with the contiguous US...")
    # Caution: this is a very large dataset, and the intersection operation can be slow...
    # It takes about 14 minutes to run on 16GB M4 Mac Mini
    contiguous_us_dissolved = contiguous_us.dissolve()
    grids_filtered = grids[grids.intersects(contiguous_us_dissolved.iloc[0].geometry)]

    # Create a GeoDataFrame with just the centroids for reprojection
    centroid_gdf = gpd.GeoDataFrame(
        geometry=grids_filtered['centroid'], 
        crs=grids_filtered.crs
    )
    logger.info(f"There are {len(grids_filtered)} centroids in total.")
    
    centroid_gdf = centroid_gdf.to_crs(epsg=4326)  # Reproject centroids to WGS84 (EPSG:4326) for real lat/lon values
    grids_filtered['cent_lon'] = centroid_gdf.geometry.x.round(4)
    grids_filtered['cent_lat'] = centroid_gdf.geometry.y.round(4)
    grids_filtered = grids_filtered.sort_values(
        by=["cent_lat", "cent_lon"],
        ascending=[False, False]
    )
    
    logger.info(f"Final GeoDataFrame contains {len(grids_filtered)} grids.")
    logger.info(f"Filtered out {len(contiguous_us) - len(grids_filtered)} grids that don't overlap with the contiguous US!")
    logger.info(f"Filtered US states data type: {type(grids_filtered)}.")
    logger.info(f"Filtered US states column data type: {grids_filtered.dtypes}.")
    logger.info("Filtered US states data summary: \n{}".format(grids_filtered.head(6)))
    logger.info("One example of a POLYGON WKT string under EPSG-5070: \n{}".format(grids_filtered['geometry'].iloc[0]))
    
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)  # Create directory if it doesn't exist
        try:
            grids_filtered.to_file(output_path, driver="ESRI Shapefile")
            logger.info(f"Saved grids data to file {output_path}!")
        except Exception as e:
            logger.error(f"Error saving shapefile: {e}")
            return None
    
    return grids_filtered