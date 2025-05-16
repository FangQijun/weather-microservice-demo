"""
Utilities for Gridpoints data parsing and validation.
"""
import os
import sys
import csv
from typing import Dict, List, Any, Optional

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)
from app.utils.log_config import setup_logging


logger = setup_logging(
    logs_dir="logs",
    logs_sub_dir="extract",
    module_name=os.path.splitext(os.path.basename(__file__))[0]
)


def parse_tsv_file(file_path: str, num_rows: int) -> List[Dict[str, Any]]:
    """
    Parse a TSV file into a list of dictionaries.
    
    Args:
        file_path (str): Path to the TSV file
        num_rows (int): Number of rows to read from the file
        
    Returns:
        List[Dict[str, Any]]: List of dictionaries with column names as keys
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
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