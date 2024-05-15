import requests
import json
import openmeteo_requests
import requests_cache
from retry_requests import retry
import statistics
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import time
import geopandas as gpd
import re
import csv


allowedDeviationPercentageOfRain = 50
allowedDeviationPercentageOfTemp = 20
allowedDeviationPercentageOfWind = 20
seaLevelRise = 10 #0.5



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
    print(f"Percentage Increse of rain: {percentrageIncreaseRain}% / {allowedDeviationPercentageOfRain}%")

    percentrageIncreaseTemp = calcPercentageIncrease(legacy_temperature_2m_max, future_temperature_2m_max)
    print(f"Percentage Increse of temp: {percentrageIncreaseTemp}% / {allowedDeviationPercentageOfTemp}%")

    percentrageIncreaseWind = calcPercentageIncrease(legacy_wind_speed_10m_max, future_wind_speed_10m_max)
    print(f"Percentage Increse of wind: {percentrageIncreaseWind}% / {allowedDeviationPercentageOfWind}%")

    stillAboveSeaLevel, _ = isStillAboveSeaLevelCords(pLat, pLong)
    print(f"Still above sea level: {stillAboveSeaLevel}")

    if(percentrageIncreaseRain < (-1)*allowedDeviationPercentageOfRain or percentrageIncreaseRain > allowedDeviationPercentageOfRain):
        livable = False
    elif(percentrageIncreaseTemp < (-1)*allowedDeviationPercentageOfTemp or percentrageIncreaseTemp > allowedDeviationPercentageOfTemp):
        livable = False
    elif(percentrageIncreaseWind < (-1)*allowedDeviationPercentageOfWind or percentrageIncreaseWind > allowedDeviationPercentageOfWind):
        livable = False
    elif(not stillAboveSeaLevel):
        livable = False

    print(f"Still livable: {livable}")

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



def isStillAboveSeaLevelCords(pLat, pLong):
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
        isStillAboveSeaLevel, elevation = isStillAboveSeaLevelCords(lat, lon)

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
        isStillAboveSeaLevel, elevation = isStillAboveSeaLevelCords(lat, lon)

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
            if not(data[i]['aboveSea']):
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

    # Speichere die Karte als HTML-Datei
    m.save(f'worldFloodMapScale{scale}.html')
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



def bruteforceCoordiantesToFile(pSteps, pSleep=1):
    df = pd.DataFrame(columns=['latitude', 'longitude', 'aboveSea', 'elevation'])

    maxSteps = (180 / pSteps) * (360 / pSteps)
    index = 0

    for i in range(-90, 90, pSteps): # latitude
        for j in range(-180, 180, pSteps): # longitude
            print(f"Status: {index} / {maxSteps} ({round(index/maxSteps*100, 3)}%)")

            elevation = bruteforceElevation(i, j)
            if(elevation == 0):
                above = True
            else:
                above = isStillAboveSeaLevelElevation(elevation)

            df.loc[index] = [i, j, above, elevation]
            index +=1
            time.sleep(pSleep)

            jsonData = df.to_json(orient='records')

            with open(f"bruteforcedCordinateScale{pSteps}.geojson", 'w') as f:
                f.write(jsonData)




# Plots the elevation data from the given file.
#plotDataFromFile('bruteforcedCordinateScale10.geojson')

# Plots the 10 biggest cities with population above 100000 people (using rain, wind, temp, sealevel)
plotLivable(getCities(100000, 10))

# Plots the 10 biggest cities with population above 100000 people (using only sealevel)
#plotOnlySeaLevel(getCities(100000, 10))

# Checks the 10 biggest cities with population above 100000 people for liveability.
#checkCityForLivable(getCities(1000000, 5))