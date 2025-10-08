# Generated migration for Portfolio transaction system

from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


def set_initial_cash_balance(apps, schema_editor):
    """Set all existing portfolios to $10,000 cash balance"""
    Portfolio = apps.get_model('zimuabull', 'Portfolio')

    for portfolio in Portfolio.objects.all():
        portfolio.cash_balance = Decimal('10000.00')
        portfolio.save(update_fields=['cash_balance'])


class Migration(migrations.Migration):

    dependencies = [
        ('zimuabull', '0015_daytradingrecommendation'),
    ]

    operations = [
        # Add cash_balance field to Portfolio
        migrations.AddField(
            model_name='portfolio',
            name='cash_balance',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15),
        ),

        # Create PortfolioTransaction model
        migrations.CreateModel(
            name='PortfolioTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_type', models.CharField(choices=[('BUY', 'Buy'), ('SELL', 'Sell'), ('CALL', 'Call'), ('PUT', 'Put')], max_length=10)),
                ('quantity', models.DecimalField(decimal_places=4, max_digits=10)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('transaction_date', models.DateField()),
                ('notes', models.TextField(blank=True, null=True)),
                ('strike_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('expiration_date', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('portfolio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='zimuabull.portfolio')),
                ('symbol', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zimuabull.symbol')),
            ],
            options={
                'ordering': ['-transaction_date', '-created_at'],
            },
        ),

        # Add indexes to PortfolioTransaction
        migrations.AddIndex(
            model_name='portfoliotransaction',
            index=models.Index(fields=['portfolio', '-transaction_date'], name='zimuabull_p_portfol_idx'),
        ),
        migrations.AddIndex(
            model_name='portfoliotransaction',
            index=models.Index(fields=['symbol', '-transaction_date'], name='zimuabull_p_symbol_idx'),
        ),

        # Modify PortfolioHolding - remove old fields, add new ones
        migrations.RemoveField(
            model_name='portfolioholding',
            name='purchase_price',
        ),
        migrations.RemoveField(
            model_name='portfolioholding',
            name='purchase_date',
        ),
        migrations.RemoveField(
            model_name='portfolioholding',
            name='purchase_notes',
        ),
        migrations.RemoveField(
            model_name='portfolioholding',
            name='sell_price',
        ),
        migrations.RemoveField(
            model_name='portfolioholding',
            name='sell_date',
        ),
        migrations.RemoveField(
            model_name='portfolioholding',
            name='sell_notes',
        ),

        # Add new fields to PortfolioHolding
        migrations.AddField(
            model_name='portfolioholding',
            name='average_cost',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='portfolioholding',
            name='first_purchase_date',
            field=models.DateField(auto_now_add=True),
            preserve_default=False,
        ),

        # Update unique constraint on PortfolioHolding
        migrations.AlterUniqueTogether(
            name='portfolioholding',
            unique_together={('portfolio', 'symbol', 'status')},
        ),

        # Run data migration to set initial cash
        migrations.RunPython(set_initial_cash_balance, reverse_code=migrations.RunPython.noop),
    ]
