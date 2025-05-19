import os
import sys
import json
import requests
import random
import argparse
import pandas as pd
import geopandas as gpd
from dotenv import load_dotenv
from time import sleep
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)
from app.utils.log_config import setup_logging


logger = setup_logging(
    logs_dir="logs",
    logs_sub_dir="extract",
    module_name=os.path.splitext(os.path.basename(__file__))[0]
)


# Environment param: User-Agent specification
load_dotenv()
UA_DOMAIN = os.environ.get("UA-DOMAIN")
UA_EMAIL = os.environ.get("UA-EMAIL")


def coords_to_wkt_polygon(obj):
    """
    Converts a list of polygons (with each polygon as a list of [lon, lat]) into WKT POLYGON string.
    Supports only simple polygons (no holes).
    
    Args:
        obj (List[List[float]]): List of Lists of coordinates representing a polygon. Each coordinate is a list of [longitude, latitude].
    
    Returns:
        str: WKT string representation of the polygon: "POLYGON ((lon1 lat1, lon2 lat2, ...))"
    """
    if not obj or not isinstance(obj, list):
        raise ValueError("Input must be a non-empty list of polygons")

    def format_ring(ring):
        return ", ".join(f"{lon} {lat}" for lon, lat in ring)

    if isinstance(obj[0][0], list):  # Multiple polygons or one polygon with exterior ring
        # Handle MultiPolygon if needed
        rings = [f"({format_ring(ring)})" for ring in obj]
        return f"POLYGON ({', '.join(rings)})"
    else:
        raise ValueError("Invalid polygon structure")


def fetch_weather_gridpoint_polygons(input_path: str, output_path: str, batch_size: int = 200, verbose: bool = False) -> bool:
    """
    Fetch weather gridpoint polygons from the National Weather Service API and save them to a TSV file.
    
    Args:
        input_path (str): Path to the input TSV file with gridpoints
        output_path (str): Path to save the output TSV file
        verbose (bool): Whether to log detailed information
    
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info("Fetching weather gridpoint polygons...")
    logger.info(f"Reading grid IDs from {input_path}...")

    df = pd.read_csv(input_path, sep="\t")
    logger.info(f"Loaded {len(df)} grids from TSV file")
    logger.info("Available columns:")
    logger.info(df.columns.tolist())
    
    # API request Headers
    headers = {
        "User-Agent": "({}, {})".format(UA_DOMAIN, UA_EMAIL),
        "Accept": "application/geo+json"
    }
    
    all_records = []
    count_success_responses, count_failed_responses = 0, 0

    for i, row in df.iterrows():
        grid_id = row['grid_id']
        grid_x = row['grid_x']
        grid_y = row['grid_y']
        
        url = f"https://api.weather.gov/gridpoints/{grid_id}/{grid_x},{grid_y}"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raise an error for bad responses
            
            json_data = response.json()
            if i % batch_size == batch_size - 1:
                logger.info(f"Fetching data for point {i + 1}/{len(df)}...")
            
            # Extract relevant data and append to the DataFrame
            record = {
                "id": json_data.get("id", ""),
                "grid_id": json_data.get("properties", {}).get("gridId", ""),
                "grid_x": json_data.get("properties", {}).get("gridX", ""),
                "grid_y": json_data.get("properties", {}).get("gridY", ""),
                "elevation": json_data.get("properties", {}).get("elevation", {}).get("value", None),
                "geometry_type": json_data.get("geometry", {}).get("type", ""),
                "geometry_coordinates": coords_to_wkt_polygon(json_data.get("geometry", {}).get("coordinates"))
            }
            all_records.append(record)
            count_success_responses += 1
            if verbose and ((i % batch_size == batch_size - 1) or (i % 20 == 19)):
                logger.info(f"Successfully fetched data for gridpoint {grid_id}/{grid_x},{grid_y}.")
            
            # Write records by batch
            if i % batch_size == batch_size - 1:
                df = pd.DataFrame(all_records)
                output_file_exists = os.path.isfile(output_path)
                df.to_csv(
                    output_path,
                    sep='\t',
                    index=False,
                    mode='a' if output_file_exists else 'w',  # Append if the output file exists, write if new
                    header=not output_file_exists  # Write header only if the output file doesn't exist
                )
                if verbose:
                    logger.info(f"Wrote {len(all_records)} records to {output_path}!")
                    logger.info(f"Success count: {count_success_responses}, Failure count: {count_failed_responses}")
                all_records = []  # Reset the list for the next batch

                sleep_duration = random.uniform(2, 4)
                logger.info(f"zzz... Sleeping for {sleep_duration:.2f} seconds to avoid hitting rate limits")
                sleep(sleep_duration)  # Sleep to avoid hitting rate limits, albeit the rate limit of NWS API is not public information
        
        except requests.exceptions.RequestException as e:
            count_failed_responses += 1
            logger.error(f"Error fetching data for gridpoint {grid_id}: {str(e)}")
            logger.info(f"Success count: {count_success_responses}, Failure count: {count_failed_responses}")
            continue
        except ValueError as ve:
            logger.error(f"Error processing data for gridpoint {grid_id}: {str(ve)}")
            logger.info(f"Success count: {count_success_responses}, Failure count: {count_failed_responses}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error for gridpoint {grid_id}: {str(e)}")
            logger.info(f"Success count: {count_success_responses}, Failure count: {count_failed_responses}")
            continue
            return False
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Weather Microservice')
    parser.add_argument('--batch-size', type=int, default=200, help='Batch size for processing gridpoints')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    timestamp_now = datetime.now().strftime("%Y%m%dT%H%M%S")
    input_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "gridpoints_file", "unique_gridpoints.tsv"
    )
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "gridpoints_file", f"gridpoint_polygons_contiguous_us_{timestamp_now}.tsv"
    )

    success = fetch_weather_gridpoint_polygons(
        input_path=input_path,
        output_path=output_path,
        batch_size=args.batch_size,
        verbose=args.verbose
    )
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())