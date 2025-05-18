import os
import sys
import argparse
import requests
import json
from dotenv import load_dotenv
from math import radians, cos, sin, asin, sqrt
from pathlib import Path

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
from app.utils.log_config import setup_logging
from src.database.timescale_db_connection import get_connection


logger = setup_logging(
    logs_dir="logs",
    logs_sub_dir="extract",
    module_name=os.path.splitext(os.path.basename(__file__))[0]
)

# Environment param: User-Agent specification
load_dotenv()
UA_DOMAIN_BACKUP = os.environ.get("UA-DOMAIN-BACKUP")
UA_EMAIL_BACKUP = os.environ.get("UA-EMAIL-BACKUP")


def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r


def find_nearest_gridpoint(conn, latitude, longitude):
    """Find the nearest gridpoint to the given coordinates"""
    logger.info(f"Finding nearest gridpoint to coordinates: ({latitude}, {longitude})")
    
    cursor = conn.cursor()
    
    # If your database has PostGIS extensions, you could use spatial queries instead
    # But for simplicity and compatibility, we'll use the haversine formula in Python
    cursor.execute("SELECT id, grid_id, grid_x, grid_y, centroid_lon, centroid_lat FROM gridpoints")
    
    nearest_id = None
    nearest_grid_id = None
    nearest_grid_x = None
    nearest_grid_y = None
    min_distance = float('inf')
    
    for row in cursor.fetchall():
        grid_id = row[1]
        grid_x = row[2]
        grid_y = row[3]
        grid_lon = row[4]
        grid_lat = row[5]
        
        distance = haversine(longitude, latitude, grid_lon, grid_lat)
        
        if distance < min_distance:
            min_distance = distance
            nearest_id = row[0]
            nearest_grid_id = grid_id
            nearest_grid_x = grid_x
            nearest_grid_y = grid_y
    
    cursor.close()
    
    if nearest_grid_id is None:
        logger.error("No gridpoints found in the database.")
        return None
    
    logger.info(f"Found nearest gridpoint: {nearest_grid_id}/{nearest_grid_x},{nearest_grid_y} at distance {min_distance:.2f} km")
    return {
        "id": nearest_id,
        "grid_id": nearest_grid_id,
        "grid_x": nearest_grid_x,
        "grid_y": nearest_grid_y,
        "distance": min_distance
    }


def fetch_weather_forecast(grid_id, grid_x, grid_y, is_hourly=False, verbose=False):
    """Fetch weather forecast from NWS API"""
    base_url = f"https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}/forecast"
    if is_hourly:
        base_url += f"/hourly"
    if verbose:
        logger.info(f"Fetching hourly forecast from: {base_url}")
    
    headers = {
        "User-Agent": "({}, {})".format(UA_DOMAIN_BACKUP, UA_EMAIL_BACKUP),
        "Accept": "application/geo+json"
    }
    
    try:
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching {'hourly' if is_hourly else 'daily'} forecast: {e}")
        return None


def save_forecast_to_file(data, file_path):
    """Save forecast data to file"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved forecast data to {file_path}")


def enrich_forecast_data(forecast_data, hourly_data, user_id, gridpoint_info):
    """
    Enrich and transform forecast data using the transform script
    """
    logger.info("Enriching forecast data using transform script")
    
    # Define paths for temporary files
    temp_enriched_path = os.path.join(project_root, "data", "enriched", "temp_enriched.json")
    os.makedirs(os.path.dirname(temp_enriched_path), exist_ok=True)
    
    daily_path = os.path.join(project_root, "data", "forecast_daily", "temp.txt")
    hourly_path = os.path.join(project_root, "data", "forecast_hourly", "temp.txt")
    
    # Run the transform script as a subprocess
    try:
        cmd = [
            "python",
            os.path.join(project_root, "app", "transform", "transform_weather_data.py"),
            "--user-id", user_id,
            "--daily-forecast-path", daily_path,
            "--hourly-forecast-path", hourly_path,
            "--grid-id", gridpoint_info["grid_id"],
            "--grid-x", str(gridpoint_info["grid_x"]),
            "--grid-y", str(gridpoint_info["grid_y"]),
            "--output-path", temp_enriched_path
        ]
        
        subprocess.run(cmd, check=True)
        
        # Load the enriched data from the file
        with open(temp_enriched_path, 'r', encoding='utf-8') as f:
            enriched_data = json.load(f)
        
        return enriched_data
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running


def process_weather_request(user_id, latitude, longitude):
    """Process a single weather request"""
    logger.info(f"Processing weather request for user {user_id} at coordinates ({latitude}, {longitude})")
    
    # Connect to the database
    conn = get_connection()
    
    try:
        # Find the nearest gridpoint
        gridpoint = find_nearest_gridpoint(conn, latitude, longitude)
        if not gridpoint:
            return False
        
        # Fetch daily forecast
        daily_forecast = fetch_weather_forecast(
            gridpoint["grid_id"], 
            gridpoint["grid_x"], 
            gridpoint["grid_y"]
        )
        
        # Fetch hourly forecast
        hourly_forecast = fetch_weather_forecast(
            gridpoint["grid_id"], 
            gridpoint["grid_x"], 
            gridpoint["grid_y"], 
            "forecast/hourly"
        )
        
        # Save forecasts to temporary files
        daily_file_path = os.path.join(project_root, "data", "forecast_daily", "temp.txt")
        hourly_file_path = os.path.join(project_root, "data", "forecast_hourly", "temp.txt")
        
        if daily_forecast:
            save_forecast_to_file(daily_forecast, daily_file_path)
        
        if hourly_forecast:
            save_forecast_to_file(hourly_forecast, hourly_file_path)
        
        # Perform data enrichment (placeholder)
        enriched_data = enrich_forecast_data(daily_forecast, hourly_forecast, user_id, gridpoint)
        
        # Persist to database (placeholder)
        persist_to_database(enriched_data, conn)
        
        return True
    except Exception as e:
        logger.error(f"Error processing weather request: {e}")
        return False
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Weather Microservice')
    parser.add_argument('--user-id', type=str, required=True, help='User ID')
    parser.add_argument('--latitude', type=float, required=True, help='Latitude')
    parser.add_argument('--longitude', type=float, required=True, help='Longitude')
    
    args = parser.parse_args()
    
    # Ensure data directories exist
    Path(os.path.join(project_root, "data", "forecast_daily")).mkdir(parents=True, exist_ok=True)
    Path(os.path.join(project_root, "data", "forecast_hourly")).mkdir(parents=True, exist_ok=True)
    
    success = process_weather_request(args.user_id, args.latitude, args.longitude)
    
    if success:
        logger.info("Weather request processed successfully")
    else:
        logger.error("Failed to process weather request")
        sys.exit(1)


if __name__ == "__main__":
    main()