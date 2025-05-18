# Weather Microservice Demo
A microservice for weather API data ETL

## Replay
### Run in a Docker container
1. Prerequisites
   - Install Docker and Docker Compose CLIs. Check if you have both CLIs by running `docker --version` and `docker-compose --version`. If not, refer to the [installation instructions](https://docs.docker.com/compose/install/). Also, ensure Docker has sufficient resources allocated (e.g., at least 2 CPUs and 4GB of memory). Adjust these settings in Docker Desktop under menu `Settings > Resources`.
   - (Optional) Install [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/) for a more interactive UI than CLIs.
   - Install Homebrew by running `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` and `brew --version` to verify installation.
   - (Optional for Local Testing) Install Python `brew install python@3.13` and `python3 --version` to verify installation.
   - (Optional for Local Testing) Install Poetry `curl -sSL https://install.python-poetry.org | python3 -` and `poetry --version` to verify installation.
2. Clone the working directory
   ```zsh
   git clone https://github.com/FangQijun/weather-microservice-demo.git
   cd weather-microservice-demo
   ```
3. Make the shell script that specifies PostgreSQL DB extensions executable.
   ```zsh
   chmod +x docker-entrypoint-initdb.d/init-extensions.sh
   ```
4. An `.env` file is not tracked by Git for safety reason. Therefore you'll have to create a `.env` file in the root directory with `touch .env` with the following content, where the `UA-DOMAIN` and `UA-EMAIL` serve as substitute to National Weather Service (NWS) API key, of which you'd ne making API calls on behalf:
   ```zsh
   UA-DOMAIN=[Your_Organization].com
   UA-EMAIL=[Your_Name]@[Your_Organization].com

   DB_HOST=timescaledb
   DB_PORT=5432
   DB_NAME=weather_db
   DB_USER=postgres
   DB_PASSWORD=postgres
   ```
5. (Optional for Local Testing, and time-consuming) Install Timescale DB locally: Follow the steps in Section `Local Testing: Local TimescaleDB Setup` of this `README` file below ↓.
6. Ensure required data files exist: Place the required `.tsv` files for gridpoints data in the gridpoints_file directory, including:
   - The mapping data between a sample of coordinates in the contiguous U.S. and NWS gridpoints, with a filename `gridpoints_contiguous_us_[YYYYMMDD]T[HHRRSS].tsv`
<!--- TODO: Add more input files needed here --->
7. At the project root directory,
   1. Run `docker-compose up --build` to always rebuild the Docker images before starting the containers in case you made changes to `Dockerfile` or the code base, then to create and start the containers as defined in your `docker-compose.yml` file. The following will occurr in the order of...
      - A PostgreSQL service with both TimescaleDB & PostGIS extensions will be spun up. 
      - The `weather-microservice` service will be spun up.
      - As defined in `Dockerfile`, `app/main.py` will be run so that...
         - A table schema for gridpoints data will be initialized.
         - Connection to Timescale DB will be tested.
         - 'gridpoints' data will be loaded into PostgreSQL DB.
         - ...
   2. (Optional) Open a second terminal tab in either `Terminal.app` or your coding GUI. Run `docker ps` to verify two services are running indeed - one says "weather-microservice-demo-app" and the other says "timescale/timescaledb-ha:pg16". If you had Docker Desktop installed, it'll show two active containers.
<!--- TODO: Add more things app/main.py does here --->
   3. (Optional) Run `docker exec -it weather-microservice bash` to enter the project root directory of the `weather-microservice` service, in case you need to play around or troubleshoot.
   4. (Optional) Run `docker exec -it timescale-db psql -U postgres -d weather_db` to log in the PostgreSQL DB `weather_db`, in case you need to run some SQL queries in it.
   5. (Optional) Run `docker logs weather-microservice` or `docker logs timescale-db` to look at the logs of the two services in case of troubleshooting.
   6. In the second terminal tab, run `docker-compose down` to stop all containers started by `docker-compose` and remove the stopped containers, networks, and default volumes to leave your system clean. Go back to the first terminal tab - you should see all Docker containers killed. If you had Docker Desktop installed, it'll say something like "The compose app is no longer running"

### Local Testing: Local TimescaleDB Setup
On macOS, run the following installation steps **locally but globally**, namely on the `Terminal.app` of your Mac device, outside a Docker container, and outside a Poetry virtual env. It will be a dreary experience, and note that **YMMV regarding the file paths** mentioned depending on the installation path of your `Homebrew`.
1. Clean up. Run `cd ~ && ls /opt/homebrew/var | grep postgresql` to check what PostgreSQL versions you've probably already installed on your Mac. For each version, uninstall it by running `brew uninstall --force postgresql@16` and `rm -rf /opt/homebrew/var/postgresql@16`

2. Use `brew` to install PostgreSQL 16.x (The highest version compatible with TimescaleDB). Download TimescaleDB from GitHub. Then build and install it with `make`
```zsh
brew update
brew install postgresql@16
brew install cmake
git clone https://github.com/timescale/timescaledb.git
cd timescaledb
git checkout $(git tag -l | grep -v '\-' | sort -V | tail -1)  # Get the latest stable release
```

3. Get the output of `find /opt/homebrew -name pg_config` to locate the `pg_config` file path such as `/opt/homebrew/Cellar/postgresql@16/16.5/bin/pg_config`. Temporarily add it to your `$PATH` and by running `export PATH="/opt/homebrew/opt/postgresql@16.9/bin:$PATH"`

4. Build and install `TimescaleDB`.
```zsh
./bootstrap
cd ./build && make
make install
```

5. Run `ls -la $(brew --prefix postgresql@16)/share/postgresql@16/extension/timescaledb*`. You should be able to see `timescaledb.control` and some `.sql` files, indicating the `TimescaleDB` extension has been installed correctly.

6. Find where the config file is by running `find $(brew --prefix)/var -name "postgresql.conf"`. In my case it was `/opt/homebrew/var/postgresql@16/postgresql.conf`.

7. Run `nano $(brew --prefix postgresql@16)/var/postgresql@16/postgresql.conf` to make sure there is a line saying `shared_preload_libraries = 'timescaledb'`. If not, edit the value of `shared_preload_libraries` parameter to `'timescaledb'`.

8. Restart PostgreSQL and ensure it's running.
```zsh
brew services restart postgresql@16
brew services list  # Confirm it’s running
pg_ctl -D /opt/homebrew/var/postgresql@16 status  # Confirm it’s running again, with PID this time
```

9. Configure language and region of PostgreSQL DB, and start PostgreSQL service one more time
```zsh
initdb /opt/homebrew/var/postgresql@16 -E utf8  # The database cluster will be initialized with locale "en_US.UTF-8". The default text search configuration will be set to "english".
```

10. Now, you're ready to spin up a TimescaleDB of your own.
```zsh
psql postgres  # Enter psql
CREATE DATABASE weather_db;  # Create your PostgreSQL database
\c weather_db  # You are now connected to database "weather_db" as user "[your_mac_username]".
CREATE EXTENSION IF NOT EXISTS timescaledb;  # If output says "CREATE EXTENSION", it's a success!
```

11. Test existence of TimescaleDB extension.
```zsh
SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';
   extname   | extversion
-------------+------------
   timescaledb | 2.21.0-dev
(1 row)
```

12. Now, let's install PostGIS. Check where your `postgresql@16` is installed with `cd ~ && brew list postgresql@16`. You shoud see something saying `/opt/homebrew/Cellar/postgresql@16/16.9/bin/pg_config`. We will use this in Step 14.

13. Create an symbolic link of `postgresql@16`.
```zsh
sudo ln -s /opt/homebrew/Cellar/postgresql@16/16.9/bin/postgres /usr/local/bin/postgres
```

14. Download a version of PostGIS known to be compatible with `postgresql@16`. Use `cmake` to build and install it.
```zsh
cd~ && rm -rf postgis
curl -L https://download.osgeo.org/postgis/source/postgis-3.4.2.tar.gz -o postgis.tar.gz
tar -xzf postgis.tar.gz
cd postgis-3.4.2
./configure --with-pgconfig=/opt/homebrew/Cellar/postgresql@16/16.9/bin/pg_config  # Or whatever output from Step 12
make
make install
```

15. Verify PostGIS compatible with `postgresql@16` was installed successfully with `find /opt/homebrew -name postgis.control | grep postgresql@16`. You should get something like `/opt/homebrew/Cellar/postgresql@16/16.9/share/postgresql@16/extension/postgis.control`.

16. Now, PostGIS extension is ready in PostgreSQL.
```zsh
psql postgres  # Enter psql
\c weather_db  # You are now connected to database "weather_db" as user "[your_mac_username]".
CREATE EXTENSION IF NOT EXISTS postgis;  # If output says "CREATE EXTENSION", it's a success!
```

17. Test existence of PostGIS extension.
```zsh
SELECT extname, extversion FROM pg_extension WHERE extname = 'postgis';
   extname | extversion
---------+------------
   postgis | 3.4.2
(1 row)
```
<!--- TODO: Clean up below this line --->
### Create a database connection module
To test the Timescale DB connection from a module
```zsh
python src/database/timescale_db_connection.py
```

### Define the schema for the gridpoints table
```zsh
python src/database/create_schema_gridpoints.py
```

### Import data in the TSV file into the gridpoints table
The app automatically finds the latest `.tsv` file (the greatest timestamp suffix) inside dir `./data/gridpoints_file` for ingestion. 
To overwrite to table `gridpoints` with the entire TSV file (~1.26 million records), 1000 records per batch.
```zsh
python app/load/load_gridpoints.py --batch-size 1000
```
To overwrite to table `gridpoints` with the first 50,000 records of the TSV file, 1000 records per batch.
```zsh
python app/load/load_gridpoints.py --batch-size 1000 --num_rows 50000
```
To **append** to table `gridpoints` with the first 30,000 records of the TSV file, 1000 records per batch.
```zsh
python app/load/load_gridpoints.py --batch-size 1000 --num_rows 30000 --mode a
```


## Thought Processes
1. It is a 2-step process to get the weather forecasts according to [this](https://www.weather.gov/documentation/services-web-api)
   1. Step 1 is to inquire which [Gridpoint](https://weather-gov.github.io/api/gridpoints) (a 2.5km x 2.5km rectangle on the map of the United States represented by an office code consisting of 3 capital letters and two integers) a specific lat/lon is located in with a payload looking like `https://api.weather.gov/points/{latitude},{longitude}`
   2. Step 2 is to obtain the grid forecast for a `gridpoint`, use the `/points` endpoint to retrieve the current grid forecast endpoint by coordinates with a payload looking like `https://api.weather.gov/gridpoints/{office}/{gridX},{gridY}/forecast` and `https://api.weather.gov/gridpoints/{office}/{gridX},{gridY}/forecast/hourly`
2. Gridpoints WFO/x/y should not be considered static but won't be updated often according to these GitHub Q&A threads [[1](https://github.com/weather-gov/api/discussions/621),[2](https://github.com/weather-gov/api/discussions/746)]
3. Given bullet points 1-2, we decided to do the following:
   1. Create our own list of 2.5km x 2.5km grids that are almost identical to said `gridpoint`s to perfectly cover the entirety of contiguous US. There are approximately 1.26M to be exact; 
   2. Every month, for each centroid of the grid, make a "Step 1" API call to get which `gridpoint` the centroid, therefore the grid corresponds to (e.g. The 2.5km x 2.5km grid near Topeka, KS `[[-97.0799, 39.7451], [-97.0803, 39.7672], [-97.109, 39.7668], [-97.1085, 39.7448], [-97.0799, 39.7451]]` corresponds to Gridpoint `TOP/32,81`). Here are two examples showcasing how the grids indeed cover up the whole country.
![New England](screenshots/Grid_Coverage_New_England_BW.png)
![Greater Boston & RI](screenshots/Grid_Coverage_Greater_Boston_RI_BW.png)
   3. With all the API responses, we can set up an SCD2 lookup table on our own database to find out which Gridpoint a requested lat/lon belongs to. To pull such mapping offline, instead of making an API call each time a request comes in, we reduced latency and enhanced reliability.

## Project References
1. [National Weather Service API](https://www.weather.gov/documentation/services-web-api)
2. National Weather Service API [forecast update schedule](https://www.weather.gov/gid/nwr_general), hourly weather forecasts are updated every hour approximately 5 minutes after the top of the hour.
3. [U.S. States coordinate polygon data](https://www.census.gov/cgi-bin/geo/shapefiles/index.php?year=2024&layergroup=States+%28and+equivalent%29) from U.S. Census.
4. Latest Docker image of Timescale DB [[1](https://hub.docker.com/r/timescale/timescaledb-ha), [2](https://github.com/timescale/timescaledb-docker-ha/)].
5. [pygris](https://walker-data.com/pygris/), a Python package to help users access US Census Bureau TIGER/Line and cartographic boundary shapefiles and load them into Python as GeoDataFrames.
6. [Google Earth Pro](https://www.google.com/earth/outreach/learn/importing-geographic-information-systems-gis-data-in-google-earth/) to visualize `.shp` files downloaded or you created yourself.
7. Web tool to [visualize WKT strings](https://wktmap.com/) of Geo-objects under various EPSG versions (namely, Coordinate Reference Systems (CRSs)). For example the two systems involved in the app are:
   1. EPSG:4326, also known as WGS 84, is a geodetic coordinate system representing latitude and longitude on the surface of the Earth.
   2. EPSG:5070 is a projected coordinate system, specifically the Albers Equal Area Conic projection for the contiguous United States, using the NAD 1983 datum.
   3. If you are a real geography nerd, check [this](https://gis.stackexchange.com/questions/378716/understanding-epsg-in-wkt) out.
8. Web tool to [stitch images](https://pinetools.com/merge-images).
9. Web tool to [show file differences](https://www.diffchecker.com/text-compare/).

## Ambitions / Improvement Opportunities