import requests
import json
import openmeteo_requests
import requests_cache
from retry_requests import retry
import statistics
import folium
import time
import re
import xarray as xr
import pandas as pd
import numpy as np
import csv



# Changes in rain fall percentage are allowed in an intervall from -50% to 50%.
allowedDeviationPercentageOfRain = 50
# Changes in temerature percentage are allowed in an intervall from -20% to 20%.
allowedDeviationPercentageOfTemp = 20
# Changes in windspeed percentage are allowed in an intervall from -20% to 20%.
allowedDeviationPercentageOfWind = 20
# The worst case increse of the sea level.
seaLevelRise = 0.5



# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)



# Calculates the median of the ten highest data points in a given data set.
def getTopTenMedian(pData):
    topTen = sorted(pData, reverse=True)[:10]
    return statistics.median(topTen)



# Queries the Open-Meteo Api for legacy (2020) weather data.
def getLegacyClimateData(pLat, pLong):
    # API url of the archive
    url = "https://archive-api.open-meteo.com/v1/archive"
    # Query Temerature, Rainfall and windspeed for 2020.
    params = {
        "latitude": pLat,
        "longitude": pLong,
        "start_date": "2020-01-01",
        "end_date": "2020-12-31",
        "daily": ["temperature_2m_max", "precipitation_sum", "wind_speed_10m_max"],
        "timezone": "Europe/Berlin"
    }

    # Save the api response (as an array)
    responses = openmeteo.weather_api(url, params=params)
    # Use 0, because no model is specified. Use [] to use multiple models.
    response = responses[0]
    # Extract the daily variables from the response.
    daily = response.Daily()

    # Save the max temperature 2m above the ground to a numpy array.
    temperature_2m_max = getTopTenMedian(response.Daily().Variables(0).ValuesAsNumpy())
    # Save the daily rain+snow fall to a numpy array.
    precipitation_sum = getTopTenMedian(response.Daily().Variables(1).ValuesAsNumpy())
    # Save the max windspeed 10m above the ground to a numpy array.
    wind_speed_10m_max = getTopTenMedian(response.Daily().Variables(2).ValuesAsNumpy())

    # Return the previously saved variables.
    return temperature_2m_max, precipitation_sum, wind_speed_10m_max



# Queries the Open-Meteo Api for future (2050) weather data.
def getFutureClimateData(pLat, pLong):
    # API url of the weather prediction
    url = "https://climate-api.open-meteo.com/v1/climate"
    # Query Temerature, Rainfall and windspeed for 2050.
    params = {
        "latitude": pLat,
        "longitude": pLong,
        "start_date": "2050-01-01",
        "end_date": "2050-12-31",
        "models": ["MRI_AGCM3_2_S"],
        "daily": ["temperature_2m_max", "precipitation_sum", "wind_speed_10m_max"],
        "timezone": "Europe/Berlin"
    }

    # Save the api response (as an array)
    responses = openmeteo.weather_api(url, params=params)
    # Use 0, because no model is specified. Use [] to use multiple models.
    response = responses[0]
    # Extract the daily variables from the response.
    daily = response.Daily()

    # Save the max temperature 2m above the ground to a numpy array.
    temperature_2m_max = getTopTenMedian(response.Daily().Variables(0).ValuesAsNumpy())
    # Save the daily rain+snow fall to a numpy array.
    precipitation_sum = getTopTenMedian(response.Daily().Variables(1).ValuesAsNumpy())
    # Save the max windspeed 10m above the ground to a numpy array.
    wind_speed_10m_max = getTopTenMedian(response.Daily().Variables(2).ValuesAsNumpy())

    # Return the previously saved variables.
    return temperature_2m_max, precipitation_sum, wind_speed_10m_max



# Calculates the difference between the two given numbers in percent
def calcPercentageIncrease(pLegacy, pFuture):
    percentage = ((pFuture - pLegacy) / pLegacy) * 100
    return round(percentage, 3)



# Checks, whether a location (given by coordinates), will still be livable in 2050.
def checkLivable(pLat, pLong):
    # Assume it's livable.
    livable = True

    # Save the legacy (2020) weather conditions, using the according function.
    legacy_temperature_2m_max, legacy_precipitation_sum, legacy_wind_speed_10m_max = getLegacyClimateData(pLat, pLong)
    # Save the future (2050) weather conditions, using the according function.
    future_temperature_2m_max, future_precipitation_sum, future_wind_speed_10m_max = getFutureClimateData(pLat, pLong)

    # Calculate the percentage difference of rain between the past and the future.
    percentrageIncreaseRain = calcPercentageIncrease(legacy_precipitation_sum, future_precipitation_sum)
    print(f"Percentage Increse of rain: {percentrageIncreaseRain}% / {allowedDeviationPercentageOfRain}%")

    # Calculate the percentage difference of temperature between the past and the future.
    percentrageIncreaseTemp = calcPercentageIncrease(legacy_temperature_2m_max, future_temperature_2m_max)
    print(f"Percentage Increse of temp: {percentrageIncreaseTemp}% / {allowedDeviationPercentageOfTemp}%")
    
    # Calculate the percentage difference of wind between the past and the future.
    percentrageIncreaseWind = calcPercentageIncrease(legacy_wind_speed_10m_max, future_wind_speed_10m_max)
    print(f"Percentage Increse of wind: {percentrageIncreaseWind}% / {allowedDeviationPercentageOfWind}%")

    # Calculate, whether the given location will be flooded or not.
    stillAboveSeaLevel, _ = isStillAboveSeaLevelCordsMeteo(pLat, pLong)
    print(f"Still above sea level: {stillAboveSeaLevel}")

    # If the rain exceeds the upper or lower bound...
    if(percentrageIncreaseRain < (-1)*allowedDeviationPercentageOfRain or percentrageIncreaseRain > allowedDeviationPercentageOfRain):
        livable = False
    # If the temperature exceeds the upper or lower bound...
    elif(percentrageIncreaseTemp < (-1)*allowedDeviationPercentageOfTemp or percentrageIncreaseTemp > allowedDeviationPercentageOfTemp):
        livable = False
    # If the wind exceeds the upper or lower bound...
    elif(percentrageIncreaseWind < (-1)*allowedDeviationPercentageOfWind or percentrageIncreaseWind > allowedDeviationPercentageOfWind):
        livable = False
    # If the location will be flooded...
    elif(not stillAboveSeaLevel):
        livable = False

    print(f"Still livable: {livable}")

    # Return, whether the location the livable or not.
    return livable



# Iterated over a bunch of locations an performs the 'livable check'
def checkCityForLivable(pLocations):
    for index, city in pLocations.iterrows():
        print(f">> City: {city['name']}")
        lat = city['latitude']
        lon = city['longitude']
        checkLivable(lat, lon)
        print("")



# Return latitude and longitude for a given city name.
def getCordinates(pName):
    # Url of Open-Meteos geocoding api
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={pName}&count=1&language=de&format=json"
    # Save the response to a variable.
    response = requests.get(url)
    # Convert the response to the json format.
    data = response.json()

    lat = data['results'][0]['latitude']
    long = data['results'][0]['longitude']

    return lat, long



def isStillAboveSeaLevelCordsMeteo(pLat, pLong):
    try:
        # Url of Open-Meteos geocoding api
        url = f"https://api.open-meteo.com/v1/elevation?latitude={pLat}&longitude={pLong}"
        # Save the response to a variable.
        response = requests.get(url)
        # Convert the response to the json format.
        elevation = response.json()['elevation'][0]
    except:
        elevation = 0

    return (elevation - seaLevelRise > 1.0), elevation



# Function to check if a given elevation is still above sea level
def isStillAboveSeaLevelElevation(pElevation, seaLevelRise=0):
    # Check if the elevation minus sea level rise is greater than 1 meter
    return (pElevation - seaLevelRise > 1)



def getCities(pMinPopulation, pLimit=100):
    # Constructing the URL for the API request
    url = f"https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/geonames-all-cities-with-a-population-1000/records?select=name%2Cpopulation%2Ccoordinates&where=population%3E{pMinPopulation}&order_by=population%20desc&limit={pLimit}"

    # Sending a GET request to the API
    response = requests.get(url)
    # Parsing the JSON response
    data = response.json()
    # Extracting the results
    results = data["results"]

    # Creating an empty DataFrame with specified column names
    df = pd.DataFrame(columns=['name', 'population', 'latitude', 'longitude'])

    # Iterating through the results and populating the DataFrame
    for i in range(len(results)):
        # Extracting city name
        name = results[i]["name"]
        # Extracting population
        pop = results[i]["population"]
        # Extracting longitude
        lon = results[i]["coordinates"]["lon"]
        # Extracting latitude
        lat = results[i]["coordinates"]["lat"]

        # Adding the extracted data to the DataFrame
        df.loc[i] = [name, pop, lat, lon]

    # Returning the populated DataFrame
    return df



def plotLivable(pLocations):
    # Create an empty map
    m = folium.Map(location=[0, 0], zoom_start=2)
    # Add a tile layer
    folium.TileLayer('cartodbpositron').add_to(m)

    numberOfItems = len(pLocations)

    # Add a circle marker for each city
    for index, city in pLocations.iterrows():
        name = city['name']
        lat = city['latitude']
        lon = city['longitude']
        # Check if the city is still above sea level and get its elevation
        isStillAboveSeaLevel, elevation = isStillAboveSeaLevelCordsMeteo(lat, lon)

        # Check if the city is considered livable
        if(checkLivable(lat, lon)):
            print(f"Area '{name}' is still good. [{index+1}/{numberOfItems}]")
            # Add a green circle marker for livable cities
            folium.CircleMarker(
                location=[lat, lon],
                radius=city['population'] * 0.000001,
                color='green',
                fill=True,
                fill_color='green'
            ).add_to(m)
        else:
            print(f"Area '{name}' won't be good [{index+1}/{numberOfItems}]")
            # Add a red circle marker for non-livable cities
            folium.CircleMarker(
                location=[lat, lon],
                radius=city['population'] * 0.000001,
                color='red',
                fill=True,
                fill_color='red'
            ).add_to(m)

    # Save the map as an HTML file and display it in the browser
    m.save('./hmtl/world_cities_map.html')
    m.show_in_browser()



def plotOnlySeaLevel(pLocations):
    # Create an empty map
    m = folium.Map(location=[0, 0], zoom_start=2)
    # Add a tile layer
    folium.TileLayer('cartodbpositron').add_to(m)

    numberOfItems = len(pLocations)

    # Add a circle marker for each city
    for index, city in pLocations.iterrows():
        name = city['name']
        lat = city['latitude']
        lon = city['longitude']
        # Check if the city is still above sea level and get its elevation
        isStillAboveSeaLevel, elevation = isStillAboveSeaLevelCordsMeteo(lat, lon)

        # Check if the city is at sea level
        if(isStillAboveSeaLevel):
            print(f"Area '{name}' is still good. [{index+1}/{numberOfItems}]")
            # Add a green circle marker for cities at sea level
            folium.CircleMarker(
                location=[lat, lon],
                radius=city['population'] * 0.000001,
                color='green',
                fill=True,
                fill_color='green'
            ).add_to(m)
        else:
            print(f"Area '{name}' won't be good [{index+1}/{numberOfItems}]")
            # Add a red circle marker for cities not at sea level
            folium.CircleMarker(
                location=[lat, lon],
                radius=city['population'] * 0.000001,
                color='red',
                fill=True,
                fill_color='red'
            ).add_to(m)

    # Save the map as an HTML file and display it in the browser
    m.save('./hmtl/world_cities_map.html')
    m.show_in_browser()



# Load GeoJSON file and extract relevant information
def useGeoJson(pFile):
    # Load GeoJSON file
    with open(pFile, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Create an empty DataFrame with specified column names
    df = pd.DataFrame(columns=['name', 'population', 'latitude', 'longitude'])

    # Extract features from the GeoJSON data
    results = data['features']
    for i in range(len(results)):
        # Extract city name
        name = results[i]['properties']['gis_name']
        # Population information might not be available in the GeoJSON
        pop = 0  # results[i]['properties'].get('population', None)
        # Extract longitude
        lon = results[i]['geometry']['coordinates'][0]
        # Extract latitude
        lat = results[i]['geometry']['coordinates'][1]

        # Add the extracted data to the DataFrame
        df.loc[i] = [name, pop, lat, lon]

    # Return the populated DataFrame
    return df



# Function to get elevation using brute force method
def bruteforceElevation(pLat, pLong):
    # Construct the URL for the API request
    url = f"https://api.open-elevation.com/api/v1/lookup?locations={pLat},{pLong}"
    
    # Send a GET request to the API and parse the JSON response
    response = requests.get(url).json()  # Assuming requests module is imported

    try:
        # Extract elevation from the response
        elevation = response['results'][0]['elevation']
        return elevation
    except:
        # If there's an error, raise an exception with the response
        raise Exception(response)






# --------------------------------------------------------------------------------------------------





# Function to check if a given location is still above sea level
def isStillAboveSeaLevelCordsLocal(pLat, pLong):
    # Construct the URL for the API request. IP here is a docker host on the local network.
    url = f"http://10.0.12.227:5000/v1/test-dataset?locations={pLat},{pLong}"
    
    # Send a GET request to the API and parse the JSON response
    response = requests.get(url)
    data = response.json()

    # Extract elevation from the response
    elevation = data['results'][0]['elevation']
    
    # Compare elevation with sea level rise threshold
    isStillAboveSeaLevel = (elevation - seaLevelRise > 1.0)
    
    return isStillAboveSeaLevel, elevation



# Function to get temperature data from a NetCDF file
def get_temperature_data(longitude, latitude):
    # Open the NetCDF file
    dataset = xr.open_dataset('temperatur-data/data-temps.nc')
    
    # Extract the variable of interest
    tasmax = dataset['tasmax']
    
    # Select the data for the specific longitude and latitude
    location = tasmax.sel(lon=longitude, lat=latitude, method='nearest')
    
    # Select the data for the time range 1.1.2020 to 24.12.2020 and 1.1.2050 to 24.12.2050
    temp2020 = location.sel(time=slice('2020-01-01', '2020-12-24'))
    temp2050 = location.sel(time=slice('2050-01-01', '2050-12-24'))
    
    # Convert to pandas DataFrame
    df2020 = temp2020.to_dataframe().reset_index()
    df2050 = temp2050.to_dataframe().reset_index()
    
    # Convert temperatures from Kelvin to Celsius
    df2020['tasmax'] = df2020['tasmax'].astype(float) -  273.15
    df2050['tasmax'] = df2050['tasmax'].astype(float) -  273.15
    
    # Find the median of the ten highest temperatures in the year 2020
    top_ten_temperatures2020 = df2020['tasmax'].nlargest(10)
    median_top_ten2020 = np.median(top_ten_temperatures2020)
    median_top_ten2020 = round(median_top_ten2020, 2)    

    # Find the median of the ten highest temperatures in the year 2050
    top_ten_temperatures2050 = df2050['tasmax'].nlargest(10)
    median_top_ten2050 = np.median(top_ten_temperatures2050)
    median_top_ten2050 = round(median_top_ten2050, 2)   

    # Calculate the percentage change between 2020 and 2050 median temperatures
    percentageChange = calcPercentageIncrease(median_top_ten2020, median_top_ten2050)

    # Check if the percentage change is within the allowed deviation range
    return (percentageChange > (-1)*allowedDeviationPercentageOfTemp) and (percentageChange < allowedDeviationPercentageOfTemp), percentageChange



# Function to iterate through coordinates, check elevation and temperature data, and write to a file
def bruteforceCoordiantesToFile(pMaxLat, pMaxLon, pSteps, pSleep=0.1):
    # Create an empty DataFrame to store results
    df = pd.DataFrame(columns=['latitude', 'longitude', 'aboveSea', 'elevation', 'tempChangeOK', 'percentageTempChange'])

    # Calculate the total number of steps
    maxSteps = (2 * pMaxLat / pSteps) * (2 * pMaxLon / pSteps)
    index = 0

    # Iterate through latitude and longitude coordinates
    for lat in range(-pMaxLat, pMaxLat, pSteps):  # latitude
        for lon in range(-pMaxLon, pMaxLon, pSteps):  # longitude
            # Check if the location is above sea level and get elevation
            above, elevation = isStillAboveSeaLevelCordsLocal(lat, lon)
            temp = 0
            tempChangeOK = False

            # If elevation is 0, consider it above sea level
            if elevation == 0:
                above = True
            else:
                # Check if temperature change is within the allowed range
                tempChangeOK, temp = get_temperature_data(lat, lon)

            # Add data to the DataFrame
            df.loc[index] = [lat, lon, above, elevation, tempChangeOK, temp]

            index += 1

            # Pause for a while to avoid overwhelming the server
            time.sleep(pSleep)

            if(index % 250 == 0):
                print(f"Status: {index} / {maxSteps} ({round(index/maxSteps*100, 3)}%)")
                # Write intermediate results to a GeoJSON file
                jsonData = df.to_json(orient='records')
                with open(f"./geojson/bruteforcedCordinate_SeaAndTemp_Scale{pSteps}.geojson", 'w') as f:
                    f.write(jsonData)

    # Write final results to a GeoJSON file
    jsonData = df.to_json(orient='records')
    with open(f"./geojson/bruteforcedCordinate_SeaAndTemp_Scale{pSteps}.geojson", 'w') as f:
        f.write(jsonData)



# Function to plot data from a file on a map
def plotDataFromFile(pFile):
    # Create a map
    m = folium.Map(location=[0, 0], zoom_start=2)
    folium.TileLayer('cartodbpositron').add_to(m)

    # Load data from the file
    with open(pFile, 'r') as f:
        data = json.load(f)

    # Extract step size from the file name
    steps = int(re.search(r'\d+', pFile).group())

    # Iterate through data points
    for i in range(len(data)):
        lat = data[i]['latitude']
        lon = data[i]['longitude']
        delta_lat = steps / 2
        delta_lon = steps / 2
        bounds = [
            (lat - delta_lat, lon - delta_lon),
            (lat + delta_lat, lon + delta_lon)
        ]

        if(data[i]['elevation'] > 0.0):
            if not(data[i]['aboveSea']):
                folium.Rectangle(
                    bounds=bounds,
                    color=None,
                    fill=True,
                    fill_color='blue',
                    fill_opacity=0.5
                ).add_to(m)                   
            elif not (data[i]['tempChangeOK']):
                folium.Rectangle(
                    bounds=bounds,
                    color=None,
                    fill=True,
                    fill_color='red',
                    fill_opacity=0.5
                ).add_to(m)                
            else:
                folium.Rectangle(
                    bounds=bounds,
                    color=None,
                    fill=True,
                    fill_color='green',
                    fill_opacity=0.5
                ).add_to(m)

    # Save the map as an HTML file
    m.save(f'./hmtl/worldFloodMapScale{steps}.html')
    # Show the map in the default browser
    m.show_in_browser()



# Function to plot data from a file on a map
def plotRawDataFromFile(pFile):
    # Create a map
    m = folium.Map(location=[0, 0], zoom_start=2)
    folium.TileLayer('cartodbpositron').add_to(m)

    # Load data from the file
    with open(pFile, 'r') as f:
        data = json.load(f)

    # Extract step size from the file name
    steps = int(re.search(r'\d+', pFile).group())
    length = len(data)
    # Iterate through data points
    for i in range(length):
        print(f"Status: {i+1} / {length} ({round((i+1)/length*100, 3)}%)")
        lat = data[i]['latitude']
        lon = data[i]['longitude']

        folium.Circle(
            location=[lat, lon],
            radius=0.001,
            color='black'
        ).add_to(m)

    # Save the map as an HTML file
    m.save(f'./html/dummy_worldFloodMapScale{steps}.html')
    # Show the map in the default browser
    m.show_in_browser()



def createDummyFile(pMaxLat, pMaxLon, pSteps):
    # Create an empty DataFrame to store results
    df = pd.DataFrame(columns=['latitude', 'longitude', 'aboveSea', 'elevation', 'tempChangeOK', 'percentageTempChange'])

    # Calculate the total number of steps
    maxSteps = (2 * pMaxLat / pSteps) * (2 * pMaxLon / pSteps)
    index = 0

    # Iterate through latitude and longitude coordinates
    for lat in range(-pMaxLat, pMaxLat, pSteps):  # latitude
        for lon in range(-pMaxLon, pMaxLon, pSteps):  # longitude
            print(f"Status: {index} / {maxSteps} ({round(index/maxSteps*100, 3)}%)")
            # Set data to None
            above = None
            elevation = None
            tempChangeOK = None
            temp = None

            # Add data to the DataFrame
            df.loc[index] = [lat, lon, above, elevation, tempChangeOK, temp]

            index += 1

    # Write final results to a GeoJSON file
    jsonData = df.to_json(orient='records')
    with open(f"./geojson/dummy_bruteforcedCordinate_SeaAndTemp_Scale{pSteps}.geojson", 'w') as f:
        f.write(jsonData)





# --------------------------------------------------------------------------------------------------





createDummyFile(90, 180, 5)
plotRawDataFromFile('./geojson/dummy_bruteforcedCordinate_SeaAndTemp_Scale5.geojson')

#bruteforceCoordiantesToFile(90, 180, 25, 0)
#plotDataFromFile('./geojson/bruteforcedCordinate_SeaAndTemp_Scale25.geojson')

#lat, lon = getCordinates('Sydney')
#checkLivable(lat, lon)
