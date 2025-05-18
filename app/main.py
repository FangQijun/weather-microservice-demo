import os
import sys
import time
import subprocess

project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.append(project_root)
from app.utils.log_config import setup_logging


logger = setup_logging(
    logs_dir="logs",
    logs_sub_dir="app",
    module_name=os.path.splitext(os.path.basename(__file__))[0]
)


def main():
    """
    Main function to run the weather microservice.
    """
    logger.info("Weather microservice is running...")
    from src.database.create_schema_gridpoints import initialize_schema
    initialize_schema()

    from src.database.timescale_db_connection import test_connection
    test_connection()

    # Run the equivalent of the bash command to load gridpoints data into the TimescaleDB
    subprocess.run(
        ["python", "app/load/load_gridpoints.py", "--batch-size", "1000", "--num_rows", "5000"],
        check=True
    )

    # A trick to keep the 'weather-microservice' container alive
    # while True:
    #     time.sleep(10)

    logger.info("Weather microservice has completed the task.")


if __name__ == "__main__":
    main()