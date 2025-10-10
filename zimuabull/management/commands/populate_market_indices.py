"""
Management command to populate market indices and their historical data.

Usage:
  python manage.py populate_market_indices --create-indices  # Create index records
  python manage.py populate_market_indices --fetch-data --days 365  # Fetch historical data
"""

from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from zimuabull.models import MarketIndex, MarketIndexData


class Command(BaseCommand):
    help = "Populate market indices and their historical data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-indices",
            action="store_true",
            help="Create standard market index records",
        )
        parser.add_argument(
            "--fetch-data",
            action="store_true",
            help="Fetch historical data for indices",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=365,
            help="Number of days of historical data to fetch (default 365)",
        )

    def handle(self, *args, **options):
        if options["create_indices"]:
            self._create_indices()

        if options["fetch_data"]:
            days = options["days"]
            self._fetch_data(days)

        if not options["create_indices"] and not options["fetch_data"]:
            self.stdout.write(self.style.WARNING("No action specified. Use --create-indices or --fetch-data"))

    def _create_indices(self):
        """Create standard market index records"""
        self.stdout.write("Creating market indices...")

        indices = [
            {
                "name": "S&P 500",
                "symbol": "^GSPC",
                "description": "Standard & Poor's 500 Index - Large cap US stocks",
                "country": "United States"
            },
            {
                "name": "NASDAQ Composite",
                "symbol": "^IXIC",
                "description": "NASDAQ Composite Index - Technology-heavy US index",
                "country": "United States"
            },
            {
                "name": "Dow Jones Industrial Average",
                "symbol": "^DJI",
                "description": "Dow Jones Industrial Average - 30 large US companies",
                "country": "United States"
            },
            {
                "name": "S&P/TSX Composite",
                "symbol": "^GSPTSE",
                "description": "Toronto Stock Exchange Composite Index",
                "country": "Canada"
            },
            {
                "name": "Russell 2000",
                "symbol": "^RUT",
                "description": "Russell 2000 Index - Small cap US stocks",
                "country": "United States"
            },
        ]

        created = 0
        for idx_data in indices:
            index, created_flag = MarketIndex.objects.get_or_create(
                symbol=idx_data["symbol"],
                defaults=idx_data
            )
            if created_flag:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  Created: {index.name} ({index.symbol})"))
            else:
                self.stdout.write(f"  Already exists: {index.name} ({index.symbol})")

        self.stdout.write(self.style.SUCCESS(f"\nCreated {created} new indices, total: {MarketIndex.objects.count()}"))

    def _fetch_data(self, days):
        """Fetch historical data for all indices"""
        self.stdout.write(f"Fetching {days} days of historical data for market indices...")
        self.stdout.write(self.style.WARNING(
            "\nNOTE: This is a template. To actually fetch data, you need to:\n"
            "1. Install a financial data library (e.g., yfinance)\n"
            "2. Uncomment the code below\n"
        ))

        indices = MarketIndex.objects.all()
        if not indices.exists():
            self.stdout.write(self.style.ERROR("No indices found. Run with --create-indices first."))
            return

        # EXAMPLE: Using yfinance (uncomment and install: pip install yfinance)
        import yfinance as yf

        total_records = 0

        for index in indices:
            self.stdout.write(f"\nFetching data for {index.name} ({index.symbol})...")

            try:
                ticker = yf.Ticker(index.symbol)

                # Fetch historical data
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)

                hist = ticker.history(start=start_date, end=end_date)

                records_created = 0
                records_updated = 0

                for date, row in hist.iterrows():
                    date_obj = date.date()

                    # Create or update
                    _data, created = MarketIndexData.objects.update_or_create(
                        index=index,
                        date=date_obj,
                        defaults={
                            "open": float(row["Open"]),
                            "high": float(row["High"]),
                            "low": float(row["Low"]),
                            "close": float(row["Close"]),
                            "volume": int(row["Volume"]) if row["Volume"] > 0 else None,
                        }
                    )

                    if created:
                        records_created += 1
                    else:
                        records_updated += 1

                total_records += records_created + records_updated
                self.stdout.write(self.style.SUCCESS(
                    f"  {index.symbol}: {records_created} created, {records_updated} updated"
                ))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error fetching {index.symbol}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\nCompleted! {total_records} total records processed"))

        # self.stdout.write("\nExample manual population:")
        # self.stdout.write("from zimuabull.models import MarketIndex, MarketIndexData")
        # self.stdout.write("from datetime import date")
        # self.stdout.write("index = MarketIndex.objects.get(symbol='^GSPC')")
        # self.stdout.write("MarketIndexData.objects.create(")
        # self.stdout.write("    index=index,")
        # self.stdout.write("    date=date.today(),")
        # self.stdout.write("    open=5000.0, high=5050.0, low=4980.0, close=5020.0, volume=1000000")
        # self.stdout.write(")")
