from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zimuabull", "0031_portfolioriskmetrics"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModelVersion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("version", models.CharField(max_length=20, unique=True)),
                ("model_file", models.CharField(max_length=255)),
                ("feature_version", models.CharField(max_length=20)),
                ("trained_at", models.DateTimeField()),
                ("training_samples", models.IntegerField()),
                ("cv_r2_mean", models.FloatField()),
                ("cv_mae_mean", models.FloatField()),
                ("deployed_at", models.DateTimeField(blank=True, null=True)),
                ("production_trades", models.IntegerField(default=0)),
                ("production_win_rate", models.FloatField(blank=True, null=True)),
                ("production_avg_return", models.FloatField(blank=True, null=True)),
                ("production_sharpe", models.FloatField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-trained_at"],
                "indexes": [
                    models.Index(fields=["feature_version", "-trained_at"], name="zimuabull_m_feature_a7f265_idx"),
                    models.Index(fields=["is_active"], name="zimuabull_m_is_acti_78b0b9_idx"),
                ],
            },
        ),
    ]
