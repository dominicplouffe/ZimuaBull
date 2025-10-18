from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("zimuabull", "0030_alter_daytradeposition_status_iborder"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortfolioRiskMetrics",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("date", models.DateField()),
                ("sharpe_ratio", models.FloatField(blank=True, null=True)),
                ("sortino_ratio", models.FloatField(blank=True, null=True)),
                ("max_drawdown", models.FloatField(blank=True, null=True)),
                ("volatility", models.FloatField(blank=True, null=True)),
                ("beta", models.FloatField(blank=True, null=True)),
                ("largest_position_pct", models.FloatField(blank=True, null=True)),
                ("sector_concentration", models.JSONField(blank=True, default=dict)),
                ("calmar_ratio", models.FloatField(blank=True, null=True)),
                ("information_ratio", models.FloatField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "portfolio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="risk_metrics",
                        to="zimuabull.portfolio",
                    ),
                ),
            ],
            options={
                "ordering": ["-date"],
                "unique_together": {("portfolio", "date")},
                "indexes": [models.Index(fields=["portfolio", "-date"], name="zimuabull_p_portfol_2d1948_idx")],
            },
        ),
    ]
