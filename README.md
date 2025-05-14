# weather-microservice-demo
A microservice for weather API data ETL

# Thought Processes
1. It is a 2-step process to get forecasts according to [this](https://www.weather.gov/documentation/services-web-api)
   1. Step 1 is to inquire which `gridpoint` (a 2.5km x 2.5km rectangle on the map of the United States represented by an office code consisting of 3 capital letters and two integers) which a specific lat/lon is located in with a payload looking like `https://api.weather.gov/points/{latitude},{longitude}`
   2. Step 2 is to obtain the grid forecast for a `gridpoint`, use the `/points` endpoint to retrieve the current grid forecast endpoint by coordinates with a payload looking like `https://api.weather.gov/gridpoints/{office}/{gridX},{gridY}/forecast` and `https://api.weather.gov/gridpoints/{office}/{gridX},{gridY}/forecast/hourly`
2. Gridpoints WFO/x/y should not be considered static but won't be updated often according to [the GitHub Q&A thread](https://github.com/weather-gov/api/discussions/621)
3. Given bullet points 1-2, we decided to do the following:
   1. Create our own list of 2.5km x 2.5km grids that are almost identical to said `gridpoint`s to perfectly cover the entirety of contiguous US. There are approximately 1.26M to be exact; 
   2. Every month, for each centroid of the grid, make a "Step 1" API call to get which `gridpoint` the centroid, therefore the grid corresponds to (e.g. The 2.5km x 2.5km grid near Topeka, KS `[[-97.0799, 39.7451], [-97.0803, 39.7672], [-97.109, 39.7668], [-97.1085, 39.7448], [-97.0799, 39.7451]]` corresponds to Gridpoint `TOP/32,81`). Here are two examples showcasing how the grids indeed cover up the whole country.
![New England](weather-microservice-demo/screenshots/Grid_Coverage_New_England_BW.png)
![Greater Boston & RI](weather-microservice-demo/screenshots/Grid_Coverage_Greater_Boston_RI_BW.png)
   3. With all the API responses, we can set up an SCD2 lookup table on our own database to find out which Gridpoint a requested lat/lon belongs to. To pull such mapping offline, instead of making an API call each time a request comes in, we reduced latency and enhanced reliability.

# Project References
1. [Google Earth Pro](https://www.google.com/earth/outreach/learn/importing-geographic-information-systems-gis-data-in-google-earth/) to visualize open-sourced `.shp` files.
2. [pygris](https://walker-data.com/pygris/), a Python package to help users access US Census Bureau TIGER/Line and cartographic boundary shapefiles and load them into Python as GeoDataFrames.
3. [U.S. States coordinate polygon data](https://www.census.gov/cgi-bin/geo/shapefiles/index.php?year=2024&layergroup=States+%28and+equivalent%29) from U.S. Census.
4. According to [this doc](https://www.weather.gov/gid/nwr_general), hourly weather forecasts are updated every hour approximately 5 minutes after the top of the hour.
5. Web tool to [stitch images](https://pinetools.com/merge-images).