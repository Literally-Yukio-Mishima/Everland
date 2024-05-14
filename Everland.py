import requests
import json
import openmeteo_requests
import requests_cache
from retry_requests import retry
import statistics


allowedDeviationPercentage = 10
seaLevelRise = 3


def getTopTenMedian(pData):
    topTen = sorted(pData, reverse=True)[:10]
    median = statistics.median(topTen)

    return round(median, 3)


# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)


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


def checkLivable(pLat, pLong):
    legacy_temperature_2m_max, legacy_precipitation_sum, legacy_wind_speed_10m_max = getLegacyClimateData(pLat, pLong)
    future_temperature_2m_max, future_precipitation_sum, future_wind_speed_10m_max = getFutureClimateData(pLat, pLong)

    if(legacy_precipitation_sum / future_precipitation_sum > allowedDeviationPercentage):
        return False
    elif(legacy_temperature_2m_max / future_temperature_2m_max > allowedDeviationPercentage):
        return False
    elif(legacy_wind_speed_10m_max / future_wind_speed_10m_max > allowedDeviationPercentage):
        return False

    return True


def getCordinates(pName):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={pName}&count=1&language=de&format=json"

    response = requests.get(url)
    data = response.json()

    lat = data['results'][0]['latitude']
    long = data['results'][0]['longitude']

    return lat, long


def isStillAboveSeaLevelCords(pLat, pLong):
    url = f"https://api.open-meteo.com/v1/elevation?latitude={pLat}&longitude={pLong}"

    # Eine GET-Anfrage an die API senden
    response = requests.get(url)

    elevation = response.json()['elevation'][0]
    print(elevation)
    return (elevation - seaLevelRise > 1)


def isStillAboveSeaLevelElevation(pElevation):
    return (pElevation - seaLevelRise > 1)


print(f"is Livable: {checkLivable(24,90)}")