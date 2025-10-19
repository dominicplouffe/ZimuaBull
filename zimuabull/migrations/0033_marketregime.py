from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("zimuabull", "0032_modelversion"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketRegime",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("date", models.DateField()),
                (
                    "regime",
                    models.CharField(
                        choices=[
                            ("BULL_TRENDING", "Bull Trending"),
                            ("BEAR_TRENDING", "Bear Trending"),
                            ("HIGH_VOL", "High Volatility"),
                            ("LOW_VOL", "Low Volatility"),
                            ("RANGING", "Ranging/Choppy"),
                        ],
                        max_length=20,
                    ),
                ),
                ("vix_level", models.FloatField(blank=True, null=True)),
                ("trend_strength", models.FloatField()),
                ("volatility_percentile", models.FloatField()),
                ("recommended_max_positions", models.IntegerField()),
                ("recommended_risk_per_trade", models.FloatField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "index",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="regimes",
                        to="zimuabull.marketindex",
                    ),
                ),
            ],
            options={
                "ordering": ["-date"],
                "unique_together": {("index", "date")},
                "indexes": [
                    models.Index(fields=["index", "-date"], name="zimuabull_m_index__d95418_idx"),
                    models.Index(fields=["regime", "-date"], name="zimuabull_m_regime_627037_idx"),
                ],
            },
        ),
    ]
