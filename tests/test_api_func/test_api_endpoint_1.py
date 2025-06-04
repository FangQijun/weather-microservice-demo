import unittest
import sys
import os
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(project_root)
from app.extract.fetch_weather_gridpoints import fetch_weather_points

class TestGridpointLookup(unittest.TestCase):
    def test_endpoint_1_works(self, lat, lon):
        timestamp_now = datetime.now().strftime("%Y%m%dT%H%M%S")
        shapefile_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "shapefile", "grids_2500m_x_2500m.shp"
        )
        output_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "gridpoints_file", f"gridpoints_contiguous_us_{timestamp_now}.tsv"
        )
        success = fetch_weather_points(
            shapefile_path=shapefile_path,
            output_path=output_path,
            batch_size=2000,
            verbose=True
        )
        self.assertEqual(success, 0)

if __name__ == '__main__':
    unittest.main()