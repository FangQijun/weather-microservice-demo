# weather-microservice-demo
A microservice for weather API data ETL

# Thought Processes
1. It is a 2-step process to get forecasts according to [this](https://www.weather.gov/documentation/services-web-api)
   1. Step 1 is to inquire which `gridpoint` (a 2.5km x 2.5km rectangle on the map of the United States represented by an office code consisting of 3 capital letters and two integers) which a specific lat/lon is located in with a payload looking like `https://api.weather.gov/points/{latitude},{longitude}`
   2. Step 2 is to obtain the grid forecast for a `gridpoint`, use the `/points` endpoint to retrieve the current grid forecast endpoint by coordinates with a payload looking like `https://api.weather.gov/gridpoints/{office}/{gridX},{gridY}/forecast` and `https://api.weather.gov/gridpoints/{office}/{gridX},{gridY}/forecast/hourly`
2. Gridpoints WFO/x/y should not be considered static according to [this](https://github.com/weather-gov/api/discussions/621)