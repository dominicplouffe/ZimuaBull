from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from zimuabull.models import MarketIndex
from zimuabull.services.market_regime import calculate_market_regimes


class Command(BaseCommand):
    help = "Calculate market regimes for configured market indices."

    def add_arguments(self, parser):
        parser.add_argument(
            "--symbol",
            type=str,
            help="Market index symbol to process (default: all indices).",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=365,
            help="Number of trailing days to process (default: 365).",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="Explicit start date (YYYY-MM-DD). Overrides --days.",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            help="Explicit end date (YYYY-MM-DD). Defaults to today.",
        )

    def handle(self, *args, **options):
        symbol = options.get("symbol")
        days = options.get("days")
        start_date_str = options.get("start_date")
        end_date_str = options.get("end_date")

        today = timezone.now().date()

        if end_date_str:
            try:
                end_date = date.fromisoformat(end_date_str)
            except ValueError:
                self.stdout.write(self.style.ERROR(f"Invalid end date: {end_date_str}"))
                return
        else:
            end_date = today

        if start_date_str:
            try:
                start_date = date.fromisoformat(start_date_str)
            except ValueError:
                self.stdout.write(self.style.ERROR(f"Invalid start date: {start_date_str}"))
                return
        else:
            start_date = end_date - timedelta(days=days)

        indices = MarketIndex.objects.all()
        if symbol:
            indices = indices.filter(symbol=symbol)

        if not indices.exists():
            self.stdout.write(self.style.ERROR("No market indices found."))
            return

        total = 0
        for index in indices:
            self.stdout.write(f"Processing {index.name} ({index.symbol}) from {start_date} to {end_date}...")
            regimes = calculate_market_regimes(index, start_date, end_date)
            self.stdout.write(
                self.style.SUCCESS(f"  Saved {len(regimes)} regime records for {index.symbol}")
            )
            total += len(regimes)

        self.stdout.write(self.style.SUCCESS(f"\nCompleted. Generated {total} regime records."))
