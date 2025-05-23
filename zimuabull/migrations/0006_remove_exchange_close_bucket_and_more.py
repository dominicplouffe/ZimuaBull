# Generated by Django 5.0.3 on 2024-08-25 19:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zimuabull", "0005_exchange_close_bucket_exchange_last_close_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="exchange",
            name="close_bucket",
        ),
        migrations.RemoveField(
            model_name="exchange",
            name="last_close",
        ),
        migrations.RemoveField(
            model_name="exchange",
            name="last_open",
        ),
        migrations.RemoveField(
            model_name="exchange",
            name="last_volume",
        ),
        migrations.RemoveField(
            model_name="exchange",
            name="obv_status",
        ),
        migrations.RemoveField(
            model_name="exchange",
            name="thirty_close_trend",
        ),
        migrations.AddField(
            model_name="symbol",
            name="close_bucket",
            field=models.CharField(
                choices=[("UP", "Up"), ("DOWN", "Down"), ("NA", "Na")],
                default="NA",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="symbol",
            name="last_close",
            field=models.FloatField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="symbol",
            name="last_open",
            field=models.FloatField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="symbol",
            name="last_volume",
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="symbol",
            name="obv_status",
            field=models.CharField(
                choices=[
                    ("BUY", "Buy"),
                    ("SELL", "Sell"),
                    ("HOLD", "Hold"),
                    ("STRONG_BUY", "Strong Buy"),
                    ("STRONG_SELL", "Strong Sell"),
                    ("NA", "Na"),
                ],
                default="NA",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="symbol",
            name="thirty_close_trend",
            field=models.FloatField(default=0),
            preserve_default=False,
        ),
    ]
