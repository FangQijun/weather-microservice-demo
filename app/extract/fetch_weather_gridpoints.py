import os
import sys
import json
import requests
import random
import pandas as pd
import geopandas as gpd
from dotenv import load_dotenv
from time import sleep
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)
from app.utils.log_config import setup_logging


logger = setup_logging(logs_dir="logs", logs_sub_dir="extract", module_name="fetch_weather_gridpoints")
pd.set_option('display.max_columns', None)


# Environment param: User-Agent specification
load_dotenv()
UA_DOMAIN = os.environ.get("UA-DOMAIN")
UA_EMAIL = os.environ.get("UA-EMAIL")


def process_nws_responses(json_strings: list[str], output_path: str, verbose=False) -> None:
    """
    Process National Weather Service API responses and write them to TSV files.
    
    Args:
        json_strings: List of JSON response strings
        output_path: Directory to save the TSV files
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)  # Create directory if it doesn't exist
    
    keys_to_extract = [
        "gridId", "gridX", "gridY", "forecast", "forecastHourly",
        "forecastOffice", "forecastGridData", "observationStations",
        "forecastZone", "timeZone", "radarStation"
    ]
    all_records = []
    
    # Extract desired fields
    for json_string in json_strings:
        try:
            json_data = json.loads(json_string)
            
            if isinstance(json_data, dict):  # All needed json_data is in key "properties"
                record = {}
                if "id" in json_data:
                    record["api_call_id"] = json_data["id"]
                if "geometry" in json_data and "coordinates" in json_data["geometry"]:
                    coordinate = json_data["geometry"]["coordinates"]
                    if len(coordinate) == 2:
                        record["centroid_lon"] = coordinate[0]
                        record["centroid_lat"] = coordinate[1]
                    else:
                        e = "Expected an array of length 2 in key 'geometry.coordinates' but got the wrong length."
                        logger.error(e)
                        raise ValueError(e)
                if "properties" in json_data:
                    properties = json_data["properties"]
                    for key in keys_to_extract:
                        record[key] = properties.get(key, "")
                    all_records.append(record)
            elif isinstance(json_data, list):
                e = "Expected key 'properties' in a dictionary but doesn't exist."
                logger.error(e)
                raise ValueError(e)
            else:
                e = "Expected a dictionary but got the wrong type."
                logger.error(e)
                raise ValueError(e)
        except json.JSONDecodeError:
            print(f"Error parsing JSON string: {json_string[:80]}...")
            continue
    
    # Write records by batch
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


def fetch_weather_points(shapefile_path, output_path, num_points_limit=None, batch_size=10, verbose=False):
    """
    Fetch NWS gridpoint for the centroids in the grid shapefile
    
    Parameters:
    -----------
    shapefile_path : str
        Path to the shapefile containing the grid points
    output_path : str
        Path to the output TSV file
    num_points_limit : int
        Number of points to process (default: None, process all points)
    batch_size : int
        Number of points to process in each batch (default: 10)
    verbose : bool
        Whether to print detailed logs (default: False)
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

    json_responses = []
    count_batch = 0
    count_failed_responses = 0
    last_index = min(num_points_limit, len(grids)) - 1 if num_points_limit else len(grids) - 1
    logger.info(f"\n\n>>> Total count of API calls: {last_index + 1}. <<<\n")

    for i in range(last_index + 1):
        lat = grids.loc[i, 'cent_lat']
        lon = grids.loc[i, 'cent_lon']
        
        url = f"https://api.weather.gov/points/{lat},{lon}"
        
        try:
            if verbose:
                logger.info(f"Fetching data for point {i + 1}/{last_index + 1}: ({lat}, {lon})")
            else:
                if i % batch_size == batch_size - 1:
                    logger.info(f"Fetching data for point {i + 1}/{last_index + 1}: ({lat}, {lon})")
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            json_string = json.dumps(response.json())
            json_responses.append(json_string)
            
            if verbose:
                logger.info(f"Response for point {i + 1}:")
                logger.info(json_string)
            
            if i % batch_size == batch_size - 1:
                sleep_duration = random.uniform(5, 8)
                logger.info(f"zzz... Sleeping for {sleep_duration:.2f} seconds to avoid hitting rate limits")
                sleep(sleep_duration)  # Sleep to avoid hitting rate limits, albeit the rate limit of NWS API is not public information
        except requests.exceptions.RequestException as e:
            count_failed_responses += 1
            logger.error(f"Error: {e}")
        
        if i % batch_size == batch_size - 1 or i == last_index:
            count_batch += 1
            logger.info(f"\n\n> Finished batch #{count_batch} (Batch size = {batch_size}): Made {len(json_responses)} successful API calls so far in this batch. <\n")
            process_nws_responses(json_responses, output_path, verbose=verbose)
            json_responses = []
    
    count_written_responses = len(pd.read_csv(output_path, sep='\t'))  # Not reading the header
    logger.info(
        f"\n\n\
        >>> Out of {last_index + 1} API calls, we caught {count_failed_responses} failed ones.\n\
        >>> Out of {last_index + 1} API calls, we recorded {count_written_responses} successful ones. <<<"
    )


if __name__ == "__main__":
    timestamp_now = datetime.now().strftime("%Y%m%dT%H%M%S")
    shapefile_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "shapefile", "grids_2500m_x_2500m.shp"
    )
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "gridpoints_file", f"gridpoints_contiguous_us{timestamp_now}.tsv"
    )
    fetch_weather_points(
        shapefile_path=shapefile_path,
        output_path=output_path,
        batch_size=200,
        verbose=False
    )