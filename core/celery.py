import os

# This muckery is required - django must be fully setup before we load the
# channels, as the channels require models, which require settings, which...
# you get the idea.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django  # noqa

django.setup()

from celery import Celery  # noqa


app = Celery("core")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_scheduler = "django_celery_beat.schedulers:DatabaseScheduler"
