"""
Utilities for Gridpoints data parsing and validation.
"""
import os
import sys
import csv
import re
from typing import Dict, List, Any, Optional

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)
from app.utils.log_config import setup_logging


logger = setup_logging(
    logs_dir="logs",
    logs_sub_dir="extract",
    module_name=os.path.splitext(os.path.basename(__file__))[0]
)


def get_most_recent_file(sub_folder: str, extension: str = '.tsv') -> Optional[str]:
    """
    Find the most recent file with the specified extension in a given subfolder of data.
    Assumes filenames end with a timestamp in format YYYYMMDDTHHMMSS.
    
    Args:
        sub_folder (str): The subfolder within the data directory to search
        extension (str): The file extension to filter by (default: '.tsv')
        
    Returns:
        Optional[str]: Full path to the most recent file, or None if no matching files found
    """
    dir_path = os.path.join(project_root, 'data', sub_folder)
    logger.info(f"Searching for files in: {dir_path}")
    
    if not os.path.isdir(dir_path):
        logger.error(f"Directory not found: {dir_path}")
        return None
    
    timestamp_pattern = re.compile(r'(\d{8}T\d{6})')
    files_with_timestamps = []
    
    for file_name in os.listdir(dir_path):
        if not file_name.endswith(extension):
            continue
        
        match = timestamp_pattern.search(file_name)
        if match:
            timestamp = match.group(1)  # Extract timestamp substrings from filename
            file_path = os.path.join(dir_path, file_name)
            files_with_timestamps.append((file_path, timestamp))
        else:
            logger.debug(f"File {file_name} doesn't contain a timestamp in expected format")
    
    if not files_with_timestamps:
        logger.warning(f"No {extension} files with timestamps found in {dir_path}")
        return None
    
    # Filename with the greatest timestamp
    most_recent_file = sorted(files_with_timestamps, key=lambda x: x[1], reverse=True)[0][0]
    logger.info(f"Found most recent file: {most_recent_file}")
    
    return str(most_recent_file)


def parse_tsv_file(file_path: str, num_rows: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Parse a TSV file into a list of dictionaries.
    
    Args:
        file_path (str): Path to the TSV file
        num_rows (Optional[int], optional): Number of rows to read from the file. 
                                           If None, all rows are read. Defaults to None.
        
    Returns:
        List[Dict[str, str]]: List of dictionaries with column names as keys
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            
            if num_rows is not None:
                # Only read the specified number of rows
                data = []
                for i, row in enumerate(reader):
                    if i >= num_rows:
                        break
                    data.append(row)
            else:
                # Read all rows
                data = list(reader)
            
            logger.info(f"Successfully parsed {len(data)} rows from {file_path}")
            return data
    except Exception as e:
        logger.error(f"Error parsing TSV file {file_path}: {str(e)}")
        raise


def validate_gridpoint_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Validate and clean a gridpoint data row.
    
    Args:
        row (Dict[str, Any]): Raw data row from TSV
        
    Returns:
        Optional[Dict[str, Any]]: Validated and cleaned row, or None if invalid
    """
    required_fields = ['api_call_id', 'centroid_lon', 'centroid_lat', 'gridId', 'gridX', 'gridY']
    
    # Check that all required fields exist and are not empty
    for field in required_fields:
        if field not in row or not row[field]:
            logger.warning(f"Missing required field: {field}")
            return None
    
    # Convert data types and normalize field names
    try:
        # Create a new dict with standardized field names and converted values
        validated_row = {
            'api_call_id': row['api_call_id'],
            'centroid_lon': float(row['centroid_lon']),
            'centroid_lat': float(row['centroid_lat']),
            'grid_id': row['gridId'],
            'grid_x': int(row['gridX']),
            'grid_y': int(row['gridY']),
            'forecast_url': row.get('forecast', None),
            'forecast_hourly_url': row.get('forecastHourly', None),
            'forecast_office_url': row.get('forecastOffice', None),
            'forecast_grid_data_url': row.get('forecastGridData', None),
            'observation_stations_url': row.get('observationStations', None),
            'forecast_zone_url': row.get('forecastZone', None),
            'time_zone': row.get('timeZone', None),
            'radar_station': row.get('radarStation', None)
        }
        return validated_row
    except (ValueError, TypeError) as e:
        logger.warning(f"Data validation error: {str(e)} for row: {row}")
        return None