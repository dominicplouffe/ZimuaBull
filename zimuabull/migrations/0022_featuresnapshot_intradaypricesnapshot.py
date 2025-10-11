import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zimuabull", "0021_symbol_latest_price_symbol_price_updated_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeatureSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trade_date", models.DateField()),
                ("features", models.JSONField(default=dict)),
                ("previous_close", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ("open_price", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ("close_price", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ("high_price", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ("low_price", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ("intraday_return", models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True)),
                ("max_favorable_excursion", models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True)),
                ("max_adverse_excursion", models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True)),
                ("feature_version", models.CharField(default="v1", max_length=20)),
                ("label_ready", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("symbol", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="feature_snapshots", to="zimuabull.symbol")),
            ],
            options={
                "ordering": ["-trade_date"],
                "unique_together": {("symbol", "trade_date", "feature_version")},
            },
        ),
        migrations.CreateModel(
            name="IntradayPriceSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("timestamp", models.DateTimeField()),
                ("price", models.DecimalField(decimal_places=4, max_digits=12)),
                ("volume", models.BigIntegerField(blank=True, null=True)),
                ("source", models.CharField(default="unknown", max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("symbol", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="intraday_snapshots", to="zimuabull.symbol")),
            ],
            options={
                "ordering": ["-timestamp"],
            },
        ),
        migrations.AddIndex(
            model_name="featuresnapshot",
            index=models.Index(fields=["trade_date"], name="zimuabull_f_trade_d_27d50c_idx"),
        ),
        migrations.AddIndex(
            model_name="featuresnapshot",
            index=models.Index(fields=["symbol", "-trade_date"], name="zimuabull_f_symbol__0a16f5_idx"),
        ),
        migrations.AddIndex(
            model_name="intradaypricesnapshot",
            index=models.Index(fields=["symbol", "-timestamp"], name="zimuabull_i_symbol__287253_idx"),
        ),
        migrations.AddIndex(
            model_name="intradaypricesnapshot",
            index=models.Index(fields=["-timestamp"], name="zimuabull_i__times_3dccaa_idx"),
        ),
    ]
