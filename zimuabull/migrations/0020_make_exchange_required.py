# Generated manually

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zimuabull", "0019_portfolio_exchange"),
    ]

    operations = [
        migrations.AlterField(
            model_name="portfolio",
            name="exchange",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="zimuabull.exchange"),
        ),
    ]
