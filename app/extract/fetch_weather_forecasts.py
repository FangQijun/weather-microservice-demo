import os
import sys
import argparse
import requests
import json
import re
import pandas as pd
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
            logger.info(f"Executing SQL query to find nearest gridpoint... \n{NEAREST_GRIDPOINT if verbose else ""}")
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
                logger.info(f"... which corresponds to the Gridpoint ID ({result_dict["grid_id"]}, {result_dict["grid_x"]}, {result_dict["grid_y"]}).")
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
            logger.info(f"Received {'hourly' if is_hourly else 'daily'} forecast response for Grid ID ({grid_id}, {grid_x},{grid_y}):")
            # logger.info(json.dumps(json_data, indent=4))
        return json_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching {'hourly' if is_hourly else 'daily'} forecast: {e}")
        return None


def parse_wind_speed(wind_speed_str: str) -> Tuple[int, int]:
    """
    Parse wind speed string to extract low and high values
    
    Args:
        wind_speed_str: Wind speed string (e.g., "5 mph" or "6 to 13 mph")
        
    Returns:
        Tuple of (wind_speed_low, wind_speed_high)
    """
    if "to" in wind_speed_str:
        match = re.search(r'(\d+)\s+to\s+(\d+)', wind_speed_str)
        if match:
            return int(match.group(1)), int(match.group(2))
    else:
        match = re.search(r'(\d+)', wind_speed_str)
        if match:
            value = int(match.group(1))
            return value, value
    
    # Default if parsing fails
    return 0, 0


def save_forecast_to_file(
        input_longitude: float, input_latitude: float,
        grid_id: str, grid_x: int, grid_y: int,
        forecast_data: Dict[str, Any], is_hourly: bool, verbose: bool = False,
    ) -> str:
    """
    Process forecast data (JSON) and save as TSV
    
    Args:
        input_longitude: Longitude coordinate in the original request
        input_latitude: Latitude coordinate in the original request
        grid_id: Grid ID (office code of weather station)
        grid_x: Grid X number
        grid_y: Grid Y number
        forecast_data: Forecast data from API
        is_hourly: Whether this is hourly forecast data
        verbose: Whether to log detailed information
        
    Returns:
        Path to the saved file
    """
    filename_substr = "forecast_" + ("hourly" if is_hourly else "daily")
    file_path = os.path.join(
        project_root, 
        "data", 
        "forecast_hourly" if is_hourly else "forecast_daily", 
        filename_substr + ".tsv"
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Store original JSON for debugging just in case
    json_path = os.path.join(
        project_root, 
        "data", 
        "forecast_hourly" if is_hourly else "forecast_daily", 
        filename_substr + "_raw.json"
    )
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(forecast_data, f, indent=4)
    if verbose:
        logger.info(f"Saved raw forecast API response to {json_path}")
    
    # Extract metadata from properties
    try:
        properties = forecast_data.get("properties", {})
        generated_at = properties.get("generatedAt", "")
        update_time = properties.get("updateTime", "")
        valid_times = properties.get("validTimes", "")
        periods = properties.get("periods", [])
    except KeyError as e:
        logger.error(f"Error extracting basic metadata under the 'properties' key from forecast data: {e}")
        return None
    
    records = []

    # Tabulation
    for period in periods:
        # Parse wind speed
        wind_speed_low, wind_speed_high = parse_wind_speed(period.get("windSpeed", "0 mph"))
        
        # Get precipitation probability
        prob_precip = None
        if period.get("probabilityOfPrecipitation") and \
            period["probabilityOfPrecipitation"].get("value") is not None:
            prob_precip = period["probabilityOfPrecipitation"]["value"]
        
        # Get dew point
        dew_point = None
        if is_hourly and period.get("dewpoint") and \
            period["dewpoint"].get("value") is not None:
            dew_point = period["dewpoint"]["value"]
        
        # Get relative humidity
        relative_humidity = None
        if is_hourly and period.get("relativeHumidity") and \
            period["relativeHumidity"].get("value") is not None:
            relative_humidity = period["relativeHumidity"]["value"]
        
        # Construct record
        record = {
            "input_longitude": input_longitude,
            "input_latitude": input_latitude,
            "grid_id": grid_id,
            "grid_x": grid_x,
            "grid_y": grid_y,
            "is_hourly": is_hourly,
            "generated_at": generated_at,
            "update_time": update_time,
            "valid_times": valid_times,
            "number": period.get("number", ""),
            "name": period.get("name", ""),
            "start_time": period.get("startTime", ""),
            "end_time": period.get("endTime", ""),
            "is_daytime": period.get("isDaytime", ""),
            "temperature": period.get("temperature", ""),
            "temperature_trend": period.get("temperatureTrend", ""),
            "probability_precipitation": prob_precip,
            "dew_point": dew_point,
            "relative_humidity": relative_humidity,
            "wind_speed_low": wind_speed_low,
            "wind_speed_high": wind_speed_high,
            "wind_direction": period.get("windDirection", ""),
            "short_forecast": period.get("shortForecast", ""),
            "detailed_forecast": period.get("detailedForecast", "")
        }
        
        records.append(record)
    
    df = pd.DataFrame(records)
    
    df.to_csv(
        file_path,
        sep='\t',
        index=False,
        mode='w',
        header=True
    )
    
    if verbose:
        logger.info(f"Processed and saved tabulated forecast data to {file_path}")
    logger.info(f"Saved {len(periods)} forecast periods to {file_path}")
    
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
            input_longitude=args.longitude,
            input_latitude=args.latitude,
            grid_id=nearest_gridpoint["grid_id"],
            grid_x=nearest_gridpoint["grid_x"],
            grid_y=nearest_gridpoint["grid_y"],
            forecast_data=forecast_data,
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