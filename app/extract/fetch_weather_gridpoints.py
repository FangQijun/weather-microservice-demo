import os
import sys
import requests
import random
import pandas as pd
import geopandas as gpd
from dotenv import load_dotenv
from time import sleep

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)
from app.utils.log_config import setup_logging


logger = setup_logging(logs_dir="logs", logs_sub_dir="extract", module_name="fetch_weather_gridpoints")
pd.set_option('display.max_columns', None)


# Environment param: User-Agent specification
load_dotenv()
UA_DOMAIN = os.environ.get("UA-DOMAIN")
UA_EMAIL = os.environ.get("UA-EMAIL")


def fetch_weather_points(shapefile_path, num_points=3, verbose=False):
    """
    Fetch NWS gridpoint for the centroids in the grid shapefile
    
    Parameters:
    -----------
    shapefile_path : str
        Path to the shapefile containing the grid points
    num_points : int
        Number of points to process (default: 3)
    """
    grids = gpd.read_file(shapefile_path)
    logger.info(f"Reading grid cetroids info from {shapefile_path}...")
    logger.info(f"Loaded {len(grids)} grid cetroids from shapefile")
    logger.info(f"Read grid cetroids data type: {type(grids)}.")
    logger.info("Available columns:")
    logger.info(grids.columns.tolist())
    logger.info("Filtered US states data summary: \n{}".format(grids.head(6)))
    
    # API request Headers
    headers = {
        "User-Agent": "({}, {})".format(UA_DOMAIN, UA_EMAIL),
        "Accept": "application/geo+json"
    }
    
    for i in range(min(num_points, len(grids))):
        lat = grids.loc[i, 'cent_lat']
        lon = grids.loc[i, 'cent_lon']
        
        url = f"https://api.weather.gov/points/{lat},{lon}"
        
        try:
            if verbose:
                logger.info(f"Fetching data for point {i + 1}/{num_points}: ({lat}, {lon})")
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            if verbose:
                logger.info(f"Response for point {i + 1}:")
                logger.info(response.json())
            
            sleep_duration = random.uniform(1, 5)
            if verbose:
                logger.info(f"zzz... Sleeping for {sleep_duration:.2f} seconds to avoid hitting rate limits")
            sleep(sleep_duration)  # Sleep to avoid hitting rate limits
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data for point ({lat}, {lon}): {e}")


if __name__ == "__main__":
    shapefile_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "shapefile", "grids_2500m_x_2500m.shp"
    )
    fetch_weather_points(
        shapefile_path=shapefile_path,
        num_points=3,
        verbose=True
    )