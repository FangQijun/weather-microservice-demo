import os
import sys
import argparse
import requests
import json
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List, Tuple

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)
from app.utils.log_config import setup_logging
from src.database.timescale_db_connection import get_connection, get_db_cursor


logger = setup_logging(
    logs_dir="logs",
    logs_sub_dir="extract",
    module_name=os.path.splitext(os.path.basename(__file__))[0]
)


load_dotenv()
UA_DOMAIN_BACKUP = os.environ.get("UA-DOMAIN-BACKUP")
UA_EMAIL_BACKUP = os.environ.get("UA-EMAIL-BACKUP")


def find_nearest_gridpoint(longitude: float, latitude: float, verbose=False) -> Optional[Dict[str, Any]]:
    """
    Find the nearest gridpoint to the given coordinates using PostGIS spatial queries
    
    Args:
        longitude: Longitude coordinate
        latitude: Latitude coordinate
        verbose: Whether to log detailed information
        
    Returns:
        Dictionary with gridpoint information or None if not found
    """
    logger.info(f"Finding nearest gridpoint to coordinates: ({longitude}, {latitude})")

    NEAREST_GRIDPOINT = """
    SELECT distances.*
    FROM (
        SELECT 
            centroid_lon, 
            centroid_lat,
            ST_Distance(
                geog,
                ST_SetSRID(ST_MakePoint({}, {}), 4326)::geography
            ) AS distance_meters,
            grid_id, 
            grid_x, 
            grid_y
        FROM 
            gridpoints
    ) AS distances
    ORDER BY distances.distance_meters
    LIMIT 1;
    """.format(longitude, latitude)
    
    with get_db_cursor(commit=False) as cursor:
        try:
            if verbose:
                logger.info(f"Executing SQL query to find nearest gridpoint: \n{NEAREST_GRIDPOINT}")
            cursor.execute(NEAREST_GRIDPOINT)
            result = cursor.fetchone()
            if result:
                result_dict = {
                    "centroid_lon": result[0],
                    "centroid_lat": result[1],
                    "distance_meters": result[2],
                    "grid_id": result[3],
                    "grid_x": result[4],
                    "grid_y": result[5]
                }
            if verbose:
                logger.info(f"Inquiry made about ({longitude}, {latitude}).")
                logger.info(f"Centroid ({result_dict["centroid_lon"]}, {result_dict["centroid_lat"]}) is the cloest pre-defined centroid to it, with a distance of {result_dict["distance_meters"]} meters.")
                logger.info(f"... which corresponds to the Gridpoint ({result_dict["grid_id"]}, {result_dict["grid_x"]}, {result_dict["grid_y"]}).")
        except Exception as e:
            logger.error(f"Error finding nearest gridpoint to ({longitude}, {latitude}): {e}")
            return None
    
    return result_dict


def fetch_weather_forecast(grid_id: str, grid_x: int, grid_y: int, is_hourly: bool = False, verbose: bool = False):
    """
    Fetch weather forecast from NWS API
    
    Args:
        grid_id: Grid ID (office code of weather station)
        grid_x: Grid X coordinate
        grid_y: Grid Y coordinate
        is_hourly: Whether to fetch hourly forecast (True) or daily forecast (False, default)
        verbose: Whether to log detailed information (False by default)
        
    Returns:
        JSON response or None if request failed
    """
    base_url = f"https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}/forecast"
    if is_hourly:
        base_url += f"/hourly"
    if verbose:
        logger.info(f"Fetching {'hourly' if is_hourly else 'daily'} forecast from: {base_url}...")
    else:
        logger.info(f"Fetching {'hourly' if is_hourly else 'daily'} forecast...")
    
    headers = {
        "User-Agent": "({}, {})".format(UA_DOMAIN_BACKUP, UA_EMAIL_BACKUP),
        "Accept": "application/geo+json"
    }
    
    try:
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()
        json_data = response.json()
        if verbose:
            logger.info(f"Response for {grid_id}/{grid_x},{grid_y}:")
            logger.info(json.dumps(json_data, indent=4))
        return json_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching {'hourly' if is_hourly else 'daily'} forecast: {e}")
        return None


def save_forecast_to_file(forecast_data: Dict[str, Any], is_hourly: bool, verbose: bool = False) -> str:
    """
    Process forecast data and save as TSV
    
    Args:
        forecast_data: Forecast data from API
        is_hourly: Whether this is hourly forecast data
        verbose: Whether to log detailed information
        
    Returns:
        Path to the saved file
    """
    file_path = os.path.join(
        project_root, 
        "data", 
        "forecast_hourly" if is_hourly else "forecast_daily", 
        "temp.txt"
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(forecast_data, f, indent=4)
    
    if verbose:
        logger.info(f"Saved forecast data to {file_path}")
    return file_path


def main():
    parser = argparse.ArgumentParser(description='Weather Microservice')
    parser.add_argument('--user-id', type=str, required=True, help='User ID')
    parser.add_argument('--longitude', type=float, required=True, help='Longitude')
    parser.add_argument('--latitude', type=float, required=True, help='Latitude')
    parser.add_argument('--is-hourly', action='store_true', help='Fetch hourly (True) or daily (False) forecast')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    
    nearest_gridpoint, forecast_data = None, None  # Initialize output variables

    nearest_gridpoint = find_nearest_gridpoint(
        longitude=args.longitude,
        latitude=args.latitude,
        verbose=args.verbose
    )
    if nearest_gridpoint:
        logger.info("Successfully found nearest Gridpoint!")
        
        forecast_data = fetch_weather_forecast(
            grid_id=nearest_gridpoint["grid_id"],
            grid_x=nearest_gridpoint["grid_x"],
            grid_y=nearest_gridpoint["grid_y"],
            is_hourly=args.is_hourly,
            verbose=args.verbose
        )
    else:
        logger.error("Failed to find nearest Gridpoint :/")
        return 1
    
    if forecast_data:
        logger.info("Successfully fetched forecast from NWS endpoint!")
        save_forecast_to_file(
            forecast_data,
            is_hourly=args.is_hourly,
            verbose=args.verbose
        )
    else:
        logger.error("Failed to fetch forecast from NWS endpoint :/")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
    # Example CLI command to run the script locally:
    # python app/extract/fetch_weather_forecasts.py --user-id abc --longitude -97.683401 --latitude 48.922601 --verbose
    # You should expect to see (FGF, 73, 155) as the closest gridpoint.