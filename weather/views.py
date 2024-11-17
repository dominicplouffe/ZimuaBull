from django.http import HttpResponse
from django.template import loader
from weather.models import Weather
from datetime import datetime, timedelta


def index(request):

    weather = Weather.objects.all().order_by("-id")[0]
    template = loader.get_template("index.html")

    daily = []
    for day in weather.daily:
        dt = datetime.fromtimestamp(day["dt"]) - timedelta(hours=4)
        dt = dt.strftime("%A")
        daily.append(
            {
                "date": dt,
                "icon": day["weather"][0]["icon"],
                "description": day["weather"][0]["description"],
                "high": int(round(day["temp"]["max"])),
                "low": int(round(day["temp"]["min"])),
            }
        )
    hourly = []
    for hour in weather.hourly:
        dt = datetime.fromtimestamp(hour["dt"]) - timedelta(hours=4)
        dt = dt.strftime("%I:%M %p")
        hourly.append(
            {
                "date": dt,
                "icon": hour["weather"][0]["icon"],
                "description": hour["weather"][0]["description"],
                "temperature": int(round(hour["temp"], 0)),
            }
        )

    weather.hourly = hourly[2:8]
    weather.daily = daily[1:7]
    context = {
        "weather": weather,
    }

    return HttpResponse(template.render(context, request))