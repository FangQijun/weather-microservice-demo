import os
import sys
import time
import subprocess
import argparse

project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.append(project_root)
from app.utils.log_config import setup_logging


logger = setup_logging(
    logs_dir="logs",
    logs_sub_dir="app",
    module_name=os.path.splitext(os.path.basename(__file__))[0]
)


def run_weather_service_demo(user_id, latitude, longitude):
    """Run the weather service with the provided parameters"""
    logger.info(f"Running weather service for user {user_id} at coordinates ({latitude}, {longitude})...")
    
    result = subprocess.run(
        [
            "python", 
            "app/weather_service.py", 
            "--user-id", user_id,
            "--latitude", str(latitude),
            "--longitude", str(longitude)
        ],
        check=False
    )
    
    if result.returncode == 0:
        logger.info("Weather service completed successfully.")
        return True
    else:
        logger.error("Weather service failed.")
        return False


def main():
    """
    Main function to run the weather microservice.
    """
    logger.info(f"Weather microservice is starting...")


    # Step 0: DB connection
    logger.info(f">>> Step 0: Setting up database connection...")
    from src.database.define_schemas import initialize_gridpoints_schema
    initialize_gridpoints_schema()

    from src.database.timescale_db_connection import test_connection
    test_connection()

    
    # Step 1: Run the equivalent of the bash command to load gridpoints data into the TimescaleDB
    logger.info(f">>> Step 1: Loading gridpoints lookup data into TimescaleDB...")
    result_1 = subprocess.run(
        ["python", "app/load/load_gridpoints.py", "--batch-size", "1000", "--num_rows", "5000"],
        # TODO: Remove the '--num_rows' argument in production, as it is only for testing purposes
        check=True
    )

    if result_1.returncode == 0:
        logger.info(f">>> Step 1: Successfully loaded gridpoints lookup data into TimescaleDB.\n")
    else:
        logger.error(f">>> Step 1: Failed to load gridpoints lookup data into TimescaleDB.\n")
        sys.exit(1)

    
    # Step 2: Run the equivalent of the bash command to extract weather data from the forecast endpoint of the NWS API
    logger.info(f">>> Step 2: Extracting weather forecast data from API...")
    user_id = "demo_user"
    latitude = 48.922601
    longitude = -97.683401
    # TODO: Does it make sense to define user_id, latitude, and longitude here?
    logger.info(f"Running weather service for user {user_id} at coordinates ({latitude}, {longitude})...")
    for is_hourly in [False, True]:
        forecast_type = "hourly" if is_hourly else "daily"
        logger.info(f"\n--- {forecast_type.capitalize()} Forecast ---\n")
        result_2 = subprocess.run(
            [
                "python", 
                "app/extract/fetch_weather_forecasts.py", 
                "--user-id", user_id,
                "--latitude", str(latitude),
                "--longitude", str(longitude)
            ] + (["--is-hourly"] if is_hourly else []) + ["--verbose"],
            check=False
        )
        
        if result_2.returncode == 0:
            logger.info(f">>> Step 2: Successfully extracted {forecast_type} weather forecast data from API.\n")
        else:
            logger.error(f">>> Step 2: Failed to extract {forecast_type} weather forecast data from API.\n")
            sys.exit(1)


    # Step 3: Run the equivalent of the bash command to load weather forecast data into the TimescaleDB
    logger.info(f">>> Step 3: Loading weather forecast data into TimescaleDB...")
    result_3 = subprocess.run(
        [
            "python", 
            "app/load/load_weather_forecasts.py", 
            "--user-id", user_id,
            "--latitude", str(latitude),
            "--longitude", str(longitude),
            "--verbose"
        ],
        check=False
    )
    
    if result_3.returncode == 0:
        logger.info(f">>> Step 3: Successfully loaded weather forecast data into TimescaleDB.\n")
    else:
        logger.error(f">>> Step 3: Failed to load weather forecast data into TimescaleDB.\n")
        sys.exit(1)

    # Trick to keep the `weather-microservice` container running indefinitely unless the user stops it
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Weather microservice stopped by user.")

    logger.info("Weather microservice has completed execution.")


if __name__ == "__main__":
    main()