import os
import logging
from grid_utils import create_us_grid


def main():
    """
    Create a grid of the contiguous United States and save it to a file.
    """
    shapefile_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
    shapefile_path = os.path.join(shapefile_dir, "shapefile", "us_states_2024_500k.shp")
    print(f"Shapefile path: {shapefile_path}")
    grid = create_us_grid(
        shapefile_path=shapefile_path,
        output_path=None
    )
    
    # print(f"Grid creation complete. Grid contains {len(grid)} cells.")


if __name__ == "__main__":
    main()