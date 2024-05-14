import requests
import json
import openmeteo_requests
import requests_cache
from retry_requests import retry
import statistics
import pandas as pd
import folium
from folium.plugins import MarkerCluster


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
    print(f"Percentage Increse of rain: {percentrageIncreaseRain}% / {allowedDeviationPercentageOfRain}%")

    percentrageIncreaseTemp = calcPercentageIncrease(legacy_temperature_2m_max, future_temperature_2m_max)
    print(f"Percentage Increse of temp: {percentrageIncreaseTemp}% / {allowedDeviationPercentageOfTemp}%")

    percentrageIncreaseWind = calcPercentageIncrease(legacy_wind_speed_10m_max, future_wind_speed_10m_max)
    print(f"Percentage Increse of wind: {percentrageIncreaseWind}% / {allowedDeviationPercentageOfWind}%")

    stillAboveSeaLevel = isStillAboveSeaLevelCords(pLat, pLong)
    print(f"Still above sea level: {stillAboveSeaLevel}")

    if(percentrageIncreaseRain < (-1)*allowedDeviationPercentageOfRain or percentrageIncreaseRain > allowedDeviationPercentageOfRain):
        livable = False
    elif(percentrageIncreaseTemp < (-1)*allowedDeviationPercentageOfTemp or percentrageIncreaseTemp > allowedDeviationPercentageOfTemp):
        livable = False
    elif(percentrageIncreaseWind < (-1)*allowedDeviationPercentageOfWind or percentrageIncreaseWind > allowedDeviationPercentageOfWind):
        livable = False
    elif(not stillAboveSeaLevel):
        livable = False

    return livable



def getCordinates(pName):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={pName}&count=1&language=de&format=json"

    response = requests.get(url)
    data = response.json()

    lat = data['results'][0]['latitude']
    long = data['results'][0]['longitude']

    return lat, long



def isStillAboveSeaLevelCords(pLat, pLong):
    url = f"https://api.open-meteo.com/v1/elevation?latitude={pLat}&longitude={pLong}"
    response = requests.get(url)
    elevation = response.json()['elevation'][0]
    return (elevation - seaLevelRise > 1.0), elevation



def isStillAboveSeaLevelElevation(pElevation):
    diff = pElevation - seaLevelRise
    return (diff > 1)



# Do not use
def getCountryCode(pCapital):
    url = f"https://restcountries.com/v3.1/capital/{pCapital}"
    response = requests.get(url)
    data = response.json()

    cca3 = data[0]['cca3']
    name = data[0]['name']['nativeName'][cca3.lower()]['common']

    return cca3, name



# Do not use
def getPopulationDensity(pCapital):
    cca3, country = getCountryCode(pCapital)
    url = f"https://stats.oecd.org/SDMX-JSON/data/POP_PROJ/{cca3}.MA+FE+TT.D199G5TT.VAR1/all?startTime=2020&endTime=2050&dimensionAtObservation=allDimensions"

    response = requests.get(url)
    data = response.json()

    population2020 = data['dataSets'][0]['observations']['0:2:0:0:0'][0]
    population2050 = data['dataSets'][0]['observations']['0:2:0:0:30'][0]

    print(f"Bevölkerung in {country} im Jahr 2020: {population2020}")
    print(f"Bevölkerung in Deutschland im Jahr 2050: {population2050}")
    print(f"Percsantage change: {calcPercentageIncrease(population2020, population2050)}%")



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


def plot():
    # Lade die Städte-Daten mit einer Mindestbevölkerung von 100000
    df_Cities = getCities(10000, 10)

    # Erstelle eine leere Karte
    m = folium.Map(location=[0, 0], zoom_start=2)

    # Füge für jede Stadt einen Kreismarker hinzu
    for index, city in df_Cities.iterrows():
        name = city['name']        
        lat = city['latitude']
        lon = city['longitude']

        isStillAboveSeaLevel, elevation = isStillAboveSeaLevelCords(lat, lon)
        if(isStillAboveSeaLevel):
            print(f"City: {name} is not flooded, its {elevation} above sea level.")
            folium.CircleMarker(
                location=[lat, lon],
                radius=city['population'] *0.0000001,  # Skaliere den Radius basierend auf der Bevölkerungszahl
                color='green',
                fill=True,
                fill_color='green'
            ).add_to(m)
        else:
            print(f"City: {name} is flooded, its {elevation} above sea level.")
            folium.CircleMarker(
                location=[lat, lon],
                radius=city['population'] *0.0000001,  # Skaliere den Radius basierend auf der Bevölkerungszahl
                color='red',
                fill=True,
                fill_color='red'
            ).add_to(m)

    # Speichere die Karte als HTML-Datei
    m.save('world_cities_map.html')

    m.show_in_browser()





#cities = ['Berlin', 'Moskau', 'London', 'Bangladesh', 'Wien']

for index, city in getCities(10000).iterrows():
    #print(f"City: {city['name']}")
    # lat, long = getCordinates(city)
    #print(f"is Livable: {checkLivable(lat,long)} \n\n")
    print("")

plot()