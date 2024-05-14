import requests
import json
import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry


# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)


def getClimateData():
    # Make sure all required weather variables are listed here
    # The order of variables in hourly or daily is important to assign them correctly below
    url = "https://climate-api.open-meteo.com/v1/climate"
    params = {
        "latitude": 52.52,
        "longitude": 13.41,
        "start_date": "2050-01-01",
        "end_date": "2050-12-31",
        "models": ["MRI_AGCM3_2_S"],
        "daily": "pressure_msl_mean"
    }
    response = openmeteo.weather_api(url, params=params)[0]

    print(f"Coordinates {response.Latitude()}°N {response.Longitude()}°E")
    print(f"Is still above sea level: {isStillAboveSeaLevel(response.Elevation())}")


def getCordinates(pName):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={pName}&count=1&language=de&format=json"

    response = requests.get(url)
    data = response.json()

    lat = data['results'][0]['latitude']
    long = data['results'][0]['longitude']

    return lat, long


def isStillAboveSeaLevel(pLat, pLong):
    url = f"https://api.open-meteo.com/v1/elevation?latitude={pLat}&longitude={pLong}"

    # Eine GET-Anfrage an die API senden
    response = requests.get(url)

    elevation = response.json()['elevation'][0]

    return (elevation - seaLevelRise > 1)


def isStillAboveSeaLevel(pElevation):
    return (pElevation - seaLevelRise > 1)


#print(f"Is still above sea level: {isStillAboveSeaLevel(latitude, longitude)}")
#lat, long = getCordinates('Berlin')
#print(f"Is still above sea level: {isStillAboveSeaLevel(10)}")