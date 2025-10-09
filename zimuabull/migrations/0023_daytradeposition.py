from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('zimuabull', '0022_featuresnapshot_intradaypricesnapshot'),
    ]

    operations = [
        migrations.CreateModel(
            name='DayTradePosition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('trade_date', models.DateField()),
                ('status', models.CharField(choices=[('OPEN', 'Open'), ('CLOSED', 'Closed'), ('CANCELLED', 'Cancelled')], default='OPEN', max_length=20)),
                ('shares', models.DecimalField(decimal_places=4, max_digits=12)),
                ('allocation', models.DecimalField(decimal_places=2, max_digits=15)),
                ('entry_price', models.DecimalField(decimal_places=4, max_digits=12)),
                ('entry_time', models.DateTimeField()),
                ('target_price', models.DecimalField(decimal_places=4, max_digits=12)),
                ('stop_price', models.DecimalField(decimal_places=4, max_digits=12)),
                ('exit_price', models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True)),
                ('exit_time', models.DateTimeField(blank=True, null=True)),
                ('exit_reason', models.CharField(blank=True, max_length=50, null=True)),
                ('confidence_score', models.FloatField()),
                ('predicted_return', models.FloatField()),
                ('recommendation_rank', models.IntegerField(default=1)),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('portfolio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='day_trade_positions', to='zimuabull.portfolio')),
                ('symbol', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='day_trade_positions', to='zimuabull.symbol')),
            ],
            options={
                'ordering': ['-trade_date', 'recommendation_rank'],
                'unique_together': {('portfolio', 'symbol', 'trade_date', 'status')},
            },
        ),
        migrations.AddIndex(
            model_name='daytradeposition',
            index=models.Index(fields=['portfolio', '-trade_date'], name='zimuabull_d_portfol_9b9eed_idx'),
        ),
        migrations.AddIndex(
            model_name='daytradeposition',
            index=models.Index(fields=['symbol', '-trade_date'], name='zimuabull_d_symbol__c8a8d4_idx'),
        ),
        migrations.AddIndex(
            model_name='daytradeposition',
            index=models.Index(fields=['status'], name='zimuabull_d_status_bace6b_idx'),
        ),
    ]
