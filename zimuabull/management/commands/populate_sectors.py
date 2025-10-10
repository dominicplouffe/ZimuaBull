"""
Management command to populate sector and industry fields for symbols.
This is a template - you'll need to integrate with a data provider like Yahoo Finance or Alpha Vantage.

Usage: python manage.py populate_sectors [--symbol AAPL] [--exchange NASDAQ]
"""

from django.core.management.base import BaseCommand

from zimuabull.models import Exchange, Symbol


class Command(BaseCommand):
    help = "Populate sector and industry fields for symbols"

    def add_arguments(self, parser):
        parser.add_argument(
            "--symbol",
            type=str,
            help="Populate for specific symbol only",
        )
        parser.add_argument(
            "--exchange",
            type=str,
            help="Populate for specific exchange only",
        )

    def handle(self, *args, **options):
        symbol_filter = options.get("symbol")
        exchange_filter = options.get("exchange")

        # Get symbols to process
        symbols = Symbol.objects.filter(sector__isnull=True)

        if symbol_filter and exchange_filter:
            exchange = Exchange.objects.get(code=exchange_filter)
            symbols = symbols.filter(symbol=symbol_filter, exchange=exchange)
        elif exchange_filter:
            exchange = Exchange.objects.get(code=exchange_filter)
            symbols = symbols.filter(exchange=exchange)
        elif symbol_filter:
            symbols = symbols.filter(symbol=symbol_filter)

        total = symbols.count()
        self.stdout.write(f"Found {total} symbols without sector/industry data")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("All symbols already have sector/industry data!"))
            return

        self.stdout.write(self.style.WARNING(
            "\nNOTE: This is a template command. To actually populate data, you need to:\n"
            "1. Install a financial data library (e.g., yfinance, alpha_vantage)\n"
            "2. Get an API key if required\n"
            "3. Uncomment and modify the code below\n"
        ))

        # EXAMPLE: Using yfinance (uncomment and install: pip install yfinance)
        import yfinance as yf

        processed = 0
        updated = 0

        for symbol_obj in symbols:
            processed += 1
            try:
                ticker = yf.Ticker(symbol_obj.symbol)
                info = ticker.info

                sector = info.get("sector")
                industry = info.get("industry")

                if sector or industry:
                    symbol_obj.sector = sector
                    symbol_obj.industry = industry
                    symbol_obj.save(update_fields=["sector", "industry", "updated_at"])
                    updated += 1
                    self.stdout.write(f"[{processed}/{total}] {symbol_obj.symbol}: {sector} - {industry}")
                else:
                    self.stdout.write(f"[{processed}/{total}] {symbol_obj.symbol}: No data available")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[{processed}/{total}] {symbol_obj.symbol}: Error - {e}"))

            # Rate limiting - adjust as needed
            if processed % 10 == 0:
                import time
                time.sleep(1)

        self.stdout.write(self.style.SUCCESS(f"\nCompleted! {updated}/{processed} symbols updated"))

        self.stdout.write("\nExample manual population:")
        self.stdout.write("from zimuabull.models import Symbol")
        self.stdout.write("symbol = Symbol.objects.get(symbol='AAPL')")
        self.stdout.write("symbol.sector = 'Technology'")
        self.stdout.write("symbol.industry = 'Consumer Electronics'")
        self.stdout.write("symbol.save()")
