import requests
from datetime import datetime
from weather.models import Weather
from core.settings import OPEN_WEATHER_MAP_URL
from celery import shared_task


@shared_task(ignore_result=True, queue="pidashtasks")
def fetch_weather():
    lat = 45.459
    lon = -75.4581

    url = OPEN_WEATHER_MAP_URL % (lat, lon)
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()

        current = data["current"]
        weather = Weather(
            name="Ottawa",
            description=current["weather"][0]["description"],
            icon=current["weather"][0]["icon"],
            temperature=current["temp"],
            lat=data["lat"],
            lon=data["lon"],
            feels_like=current["feels_like"],
            humidity=current["humidity"],
            pressure=current["pressure"],
            wind_speed=current["wind_speed"],
            wind_direction=current["wind_deg"],
            cloud_cover=current["clouds"],
            visibility=current["visibility"],
            uv_index=current["uvi"],
            sunrise=datetime.fromtimestamp(current["sunrise"]),
            sunset=datetime.fromtimestamp(current["sunset"]),
            minutely=data["minutely"],
            hourly=data["hourly"],
            daily=data["daily"],
        )
        weather.save()