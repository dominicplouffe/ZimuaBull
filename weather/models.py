from django.db import models
from django.db.models import JSONField

# Create your models here.
class Weather(models.Model):
    class Meta:
        verbose_name_plural = "Weather"

    def __str__(self):
        return self.name

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=200)
    icon = models.CharField(max_length=200)
    temperature = models.FloatField()
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lon = models.DecimalField(max_digits=9, decimal_places=6)
    feels_like = models.FloatField()

    humidity = models.IntegerField()
    pressure = models.IntegerField()
    wind_speed = models.IntegerField()
    wind_direction = models.IntegerField()
    cloud_cover = models.IntegerField()
    visibility = models.IntegerField()
    uv_index = models.IntegerField()
    sunrise = models.DateTimeField()
    sunset = models.DateTimeField()
    minutely = JSONField()
    hourly = JSONField()
    daily = JSONField()
    updated = models.DateTimeField(auto_now=True)