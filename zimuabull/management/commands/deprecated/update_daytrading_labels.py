"""
Django management command to update labels for day trading feature snapshots.

This command populates the label fields (intraday_return, max_favorable_excursion,
max_adverse_excursion) for FeatureSnapshot records on a given trade date using
finalized DaySymbol data.

Usage:
  python manage.py update_daytrading_labels --date 2024-10-10
  python manage.py update_daytrading_labels --date 2024-10-10 --symbol AAPL --exchange NASDAQ
"""

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from zimuabull.daytrading.feature_builder import update_labels_for_date
from zimuabull.models import Symbol


class Command(BaseCommand):
    help = "Update labels for day trading feature snapshots for a given date"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            required=True,
            help="Trade date in YYYY-MM-DD format (e.g., 2024-10-10)"
        )
        parser.add_argument(
            "--symbol",
            type=str,
            help="Optional: Update labels for specific symbol only"
        )
        parser.add_argument(
            "--exchange",
            type=str,
            help="Optional: Exchange code (required if --symbol is specified)"
        )

    def handle(self, *args, **options):
        date_str = options["date"]
        symbol_ticker = options.get("symbol")
        exchange_code = options.get("exchange")

        # Parse date
        try:
            trade_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise CommandError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")

        # Get symbol if specified
        symbols = None
        if symbol_ticker:
            if not exchange_code:
                raise CommandError("--exchange is required when --symbol is specified")

            try:
                symbol = Symbol.objects.get(symbol=symbol_ticker, exchange__code=exchange_code)
                symbols = [symbol]
                self.stdout.write(f"Updating labels for {symbol_ticker}:{exchange_code} on {trade_date}")
            except Symbol.DoesNotExist:
                raise CommandError(f"Symbol {symbol_ticker}:{exchange_code} not found")
        else:
            self.stdout.write(f"Updating labels for all symbols on {trade_date}")

        # Update labels
        try:
            updated_count = update_labels_for_date(trade_date, symbols=symbols)

            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccess! Updated {updated_count} feature snapshot(s) for {trade_date}"
                )
            )

            if updated_count == 0:
                self.stdout.write(
                    self.style.WARNING(
                        "\nNo feature snapshots found to update. "
                        "Make sure you've run 'generate_daytrading_features' first."
                    )
                )
        except Exception as e:
            raise CommandError(f"Failed to update labels: {e}")
