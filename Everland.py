import requests
import json
import openmeteo_requests
import requests_cache
from retry_requests import retry
import statistics
import pandas as pd
import folium
import time
import re
import xarray as xr
import pandas as pd
import numpy as np
import json
import csv



allowedDeviationPercentageOfRain = 50
allowedDeviationPercentageOfTemp = 20
allowedDeviationPercentageOfWind = 20
seaLevelRise = 0.5



# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)



def getTopTenMedian(pData):
    topTen = sorted(pData, reverse=True)[:10]
    return statistics.median(topTen)



def getLegacyClimateData(pLat, pLong):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": pLat,
        "longitude": pLong,
        "start_date": "2020-01-01",
        "end_date": "2020-12-31",
        "daily": ["temperature_2m_max", "precipitation_sum", "wind_speed_10m_max"],
        "timezone": "Europe/Berlin"
    }

    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]
    daily = response.Daily()

    temperature_2m_max = getTopTenMedian(response.Daily().Variables(0).ValuesAsNumpy())
    precipitation_sum = getTopTenMedian(response.Daily().Variables(1).ValuesAsNumpy())
    wind_speed_10m_max = getTopTenMedian(response.Daily().Variables(2).ValuesAsNumpy())

    return temperature_2m_max, precipitation_sum, wind_speed_10m_max



def getFutureClimateData(pLat, pLong):
    url = "https://climate-api.open-meteo.com/v1/climate"
    params = {
        "latitude": pLat,
        "longitude": pLong,
        "start_date": "2050-01-01",
        "end_date": "2050-12-31",
        "models": ["MRI_AGCM3_2_S"],
        "daily": ["temperature_2m_max", "precipitation_sum", "wind_speed_10m_max"],
        "timezone": "Europe/Berlin"
    }

    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]
    daily = response.Daily()

    temperature_2m_max = getTopTenMedian(response.Daily().Variables(0).ValuesAsNumpy())
    precipitation_sum = getTopTenMedian(response.Daily().Variables(1).ValuesAsNumpy())
    wind_speed_10m_max = getTopTenMedian(response.Daily().Variables(2).ValuesAsNumpy())

    return temperature_2m_max, precipitation_sum, wind_speed_10m_max



def calcPercentageIncrease(pLegacy, pFuture):
    percentage = ((pFuture - pLegacy) / pLegacy) * 100
    return round(percentage, 3)



def checkLivable(pLat, pLong):
    livable = True

    legacy_temperature_2m_max, legacy_precipitation_sum, legacy_wind_speed_10m_max = getLegacyClimateData(pLat, pLong)
    future_temperature_2m_max, future_precipitation_sum, future_wind_speed_10m_max = getFutureClimateData(pLat, pLong)

    percentrageIncreaseRain = calcPercentageIncrease(legacy_precipitation_sum, future_precipitation_sum)
    #print(f"Percentage Increse of rain: {percentrageIncreaseRain}% / {allowedDeviationPercentageOfRain}%")

    percentrageIncreaseTemp = calcPercentageIncrease(legacy_temperature_2m_max, future_temperature_2m_max)
    #print(f"Percentage Increse of temp: {percentrageIncreaseTemp}% / {allowedDeviationPercentageOfTemp}%")

    percentrageIncreaseWind = calcPercentageIncrease(legacy_wind_speed_10m_max, future_wind_speed_10m_max)
    #print(f"Percentage Increse of wind: {percentrageIncreaseWind}% / {allowedDeviationPercentageOfWind}%")

    stillAboveSeaLevel, _ = isStillAboveSeaLevelCordsMeteo(pLat, pLong)
    #print(f"Still above sea level: {stillAboveSeaLevel}")

    if(percentrageIncreaseRain < (-1)*allowedDeviationPercentageOfRain or percentrageIncreaseRain > allowedDeviationPercentageOfRain):
        livable = False
    elif(percentrageIncreaseTemp < (-1)*allowedDeviationPercentageOfTemp or percentrageIncreaseTemp > allowedDeviationPercentageOfTemp):
        livable = False
    elif(percentrageIncreaseWind < (-1)*allowedDeviationPercentageOfWind or percentrageIncreaseWind > allowedDeviationPercentageOfWind):
        livable = False
    elif(not stillAboveSeaLevel):
        livable = False

    #print(f"Still livable: {livable}")

    return livable



def checkCityForLivable(pLocations):
    for index, city in pLocations.iterrows():
        print(f">> City: {city['name']}")
        lat = city['latitude']
        lon = city['longitude']
        checkLivable(lat, lon)
        print("")



def getCordinates(pName):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={pName}&count=1&language=de&format=json"

    response = requests.get(url)
    data = response.json()

    lat = data['results'][0]['latitude']
    long = data['results'][0]['longitude']

    return lat, long



def isStillAboveSeaLevelCordsMeteo(pLat, pLong):
    try:
        url = f"https://api.open-meteo.com/v1/elevation?latitude={pLat}&longitude={pLong}"
        response = requests.get(url)
        elevation = response.json()['elevation'][0]
    except:
        elevation = 0

    return (elevation - seaLevelRise > 1.0), elevation


def isStillAboveSeaLevelElevation(pElevation, seaLevelRise=0):
    return (pElevation - seaLevelRise > 1)



def getCities(pMinPopulation, pLimit=100):
    url = f"https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/geonames-all-cities-with-a-population-1000/records?select=name%2Cpopulation%2Ccoordinates&where=population%3E{pMinPopulation}&order_by=population%20desc&limit={pLimit}"

    response = requests.get(url)
    data = response.json()
    results = data["results"]

    df = pd.DataFrame(columns=['name', 'population', 'latitude', 'longitude'])

    for i in range(len(results)):
        name = results[i]["name"]
        pop = results[i]["population"]
        lon = results[i]["coordinates"]["lon"]
        lat = results[i]["coordinates"]["lat"]

        df.loc[i] = [name, pop, lat, lon]

    return df



def plotLivable(pLocations):
    # Erstelle eine leere Karte
    m = folium.Map(location=[0, 0], zoom_start=2)
    folium.TileLayer('cartodbpositron').add_to(m)

    numberOfItems = len(pLocations)

    # Füge für jede Stadt einen Kreismarker hinzu
    for index, city in pLocations.iterrows():
        name = city['name']
        lat = city['latitude']
        lon = city['longitude']
        isStillAboveSeaLevel, elevation = isStillAboveSeaLevelCordsMeteo(lat, lon)

        if(checkLivable(lat, lon)):
            print(f"Area '{name}' is still good. [{index+1}/{numberOfItems}]")
            folium.CircleMarker(
                location=[lat, lon],
                radius=city['population'] *0.000001,
                color='green',
                fill=True,
                fill_color='green'
            ).add_to(m)
        else:
            print(f"Area '{name}' wont be good [{index+1}/{numberOfItems}]")
            folium.CircleMarker(
                location=[lat, lon],
                radius=city['population'] *0.000001,
                color='red',
                fill=True,
                fill_color='red'
            ).add_to(m)

    # Speichere die Karte als HTML-Datei
    m.save('world_cities_map.html')
    m.show_in_browser()



def plotOnlySeaLevel(pLocations):
    # Erstelle eine leere Karte
    m = folium.Map(location=[0, 0], zoom_start=2)
    folium.TileLayer('cartodbpositron').add_to(m)

    numberOfItems = len(pLocations)

    # Füge für jede Stadt einen Kreismarker hinzu
    for index, city in pLocations.iterrows():
        name = city['name']
        lat = city['latitude']
        lon = city['longitude']
        isStillAboveSeaLevel, elevation = isStillAboveSeaLevelCordsMeteo(lat, lon)

        if(isStillAboveSeaLevel):
            print(f"Area '{name}' is still good. [{index+1}/{numberOfItems}]")
            folium.CircleMarker(
                location=[lat, lon],
                radius=city['population'] *0.000001,
                color='green',
                fill=True,
                fill_color='green'
            ).add_to(m)
        else:
            print(f"Area '{name}' wont be good [{index+1}/{numberOfItems}]")
            folium.CircleMarker(
                location=[lat, lon],
                radius=city['population'] *0.000001,
                color='red',
                fill=True,
                fill_color='red'
            ).add_to(m)

    # Speichere die Karte als HTML-Datei
    m.save('world_cities_map.html')
    m.show_in_browser()
    


def useGeoJson(pFile):
    # Load GeoJSON file
    with open(pFile, 'r', encoding='utf-8') as f:
        data = json.load(f)

    df = pd.DataFrame(columns=['name', 'population', 'latitude', 'longitude'])

    results = data['features']
    for i in range(len(results)):
        name = results[i]['properties']['gis_name']
        pop = 0 #results[i]['properties'].get('population', None)
        lon = results[i]['geometry']['coordinates'][0]
        lat = results[i]['geometry']['coordinates'][1]

        df.loc[i] = [name, pop, lat, lon]

    return df



def bruteforceElevation(pLat, pLong):
    url = f"https://api.open-elevation.com/api/v1/lookup?locations={pLat},{pLong}"
    response = requests.get(url).json()
    try:
        return response['results'][0]['elevation']
    except:
        raise Exception(response)





# -----------------------------------------------------------------------------------------------





def isStillAboveSeaLevelCordsLocal(pLat, pLong):
    url = f"http://10.0.12.227:5000/v1/test-dataset?locations={pLat},{pLong}"
    response = requests.get(url)
    data = response.json()

    elevation = data['results'][0]['elevation']
    return (elevation - seaLevelRise > 1.0), elevation



def get_temperature_data(longitude, latitude):
    # Open the NetCDF file
    dataset = xr.open_dataset('temperatur-data/data-temps.nc')
    
    # Extract the variable of interest
    tasmax = dataset['tasmax']
    
    # Select the data for the specific longitude and latitude
    location = tasmax.sel(lon=longitude, lat=latitude, method='nearest')
    
    # Select the data for the time range 1.1.2050 to 24.12.2050
    temp2020 = location.sel(time=slice('2020-01-01', '2020-12-24'))
    temp2050 = location.sel(time=slice('2050-01-01', '2050-12-24'))
    
    # Convert to pandas DataFrame
    df2020 = temp2020.to_dataframe().reset_index()
    df2050 = temp2050.to_dataframe().reset_index()
    
    # Convert temperatures from Kelvin to Celsius
    df2020['tasmax'] = df2020['tasmax'].astype(float) -  273.15
    df2050['tasmax'] = df2050['tasmax'].astype(float) -  273.15
    
    # Find the median of the ten highest temperatures in the year 2050
    top_ten_temperatures2020 = df2020['tasmax'].nlargest(10)
    median_top_ten2020 = np.median(top_ten_temperatures2020)
    median_top_ten2020 = round(median_top_ten, 2)    

    # Find the median of the ten highest temperatures in the year 2050
    top_ten_temperatures2050 = df2050['tasmax'].nlargest(10)
    median_top_ten2050 = np.median(top_ten_temperatures2050)
    median_top_ten2050 = round(median_top_ten2050, 2)   

    percentageChange = calcPercentageIncrease(median_top_ten2020, median_top_ten2050)

    return (percentageChange > (-1)*allowedDeviationPercentageOfTemp) and (percentageChange < allowedDeviationPercentageOfTemp), percentageChange



def bruteforceCoordiantesToFile(pSteps, pSleep=0.1):
    df = pd.DataFrame(columns=['latitude', 'longitude', 'aboveSea', 'elevation', 'tempChangeOK', 'percentageTempChange'])

    maxSteps = (180 / pSteps) * (360 / pSteps)
    index = 0

    for lat in range(-90, 90, pSteps): # latitude
        for lon in range(-180, 180, pSteps): # longitude
            above, elevation = isStillAboveSeaLevelCordsLocal(lat, lon)
            temp = 0
            tempChangeOK = False
            
            if(elevation == 0):
                above = True
            else:
                tempChangeOK, temp = get_temperature_data(lat, lon)

            df.loc[index] = [lat, lon, above, elevation, tempChangeOK, temp]
            
            index +=1
            
            time.sleep(pSleep)

            if(index % 250 == 0):
                print(f"Status: {index} / {maxSteps} ({round(index/maxSteps*100, 3)}%)")
                jsonData = df.to_json(orient='records')
                with open(f"bruteforcedCordinate_SeaAndTemp_Scale{pSteps}.geojson", 'w') as f:
                    f.write(jsonData)



def plotDataFromFile(pFile):
    m = folium.Map(location=[0, 0], zoom_start=2)
    folium.TileLayer('cartodbpositron').add_to(m)

    with open(pFile, 'r') as f:
        data = json.load(f)

    steps = int(re.search(r'\d+', pFile).group())

    # Füge für jede Stadt einen Marker hinzu
    for i in range(len(data)):
        lat = data[i]['latitude']
        lon = data[i]['longitude']
        delta_lat = steps / 2
        delta_lon = steps / 2
        bounds = [
            (lat - delta_lat, lon - delta_lon),
            (lat + delta_lat, lon + delta_lon)
        ]

        if(data[i]['elevation'] != 0):
            if(data[i]['aboveSea'] and data[i]['tempChangeOK']):
                folium.Rectangle(
                    bounds=bounds,
                    color=None,
                    fill=True,
                    fill_color='green',
                    fill_opacity=0.5
                ).add_to(m)
            else:
                folium.Rectangle(
                    bounds=bounds,
                    color=None,
                    fill=True,
                    fill_color='red',
                    fill_opacity=0.5
                ).add_to(m)

    # Speichere die Karte als HTML-Datei
    m.save(f'worldFloodMapScale{steps}.html')
    m.show_in_browser()





bruteforceCoordiantesToFile(25, 0)
plotDataFromFile('bruteforcedCordinate_SeaAndTemp_Scale25.geojson')