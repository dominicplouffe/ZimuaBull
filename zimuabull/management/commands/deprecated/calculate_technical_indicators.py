"""
Management command to calculate RSI and MACD for all DaySymbol records.
Usage: python manage.py calculate_technical_indicators [--symbol AAPL] [--exchange NASDAQ]
"""


from django.core.management.base import BaseCommand

from zimuabull.models import DaySymbol, Symbol


class Command(BaseCommand):
    help = "Calculate RSI and MACD technical indicators for all DaySymbol records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--symbol",
            type=str,
            help="Calculate for specific symbol only",
        )
        parser.add_argument(
            "--exchange",
            type=str,
            help="Calculate for specific exchange only (requires --symbol if used)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recalculate even if values already exist",
        )

    def handle(self, *args, **options):
        symbol_filter = options.get("symbol")
        exchange_filter = options.get("exchange")
        force = options.get("force", False)

        # Get symbols to process
        symbols = Symbol.objects.all()

        if symbol_filter and exchange_filter:
            symbols = symbols.filter(symbol=symbol_filter, exchange__code=exchange_filter)
        elif symbol_filter:
            symbols = symbols.filter(symbol=symbol_filter)

        total_symbols = symbols.count()
        self.stdout.write(f"Processing {total_symbols} symbols...")

        symbols_processed = 0
        records_updated = 0

        for symbol in symbols:
            symbols_processed += 1

            # Get all days for this symbol, ordered by date
            if force:
                days = DaySymbol.objects.filter(symbol=symbol).order_by("date")
            else:
                # Only process days without RSI/MACD
                days = DaySymbol.objects.filter(
                    symbol=symbol,
                    rsi__isnull=True
                ).order_by("date")

            if not days.exists():
                continue

            self.stdout.write(f"[{symbols_processed}/{total_symbols}] {symbol.symbol}:{symbol.exchange.code} - {days.count()} days")

            for day in days:
                # Calculate RSI (needs 14 days minimum)
                rsi = DaySymbol.calculate_rsi(symbol, day.date, period=14)

                # Calculate MACD (needs 35 days minimum: 26 slow + 9 signal)
                macd, macd_signal, macd_histogram = DaySymbol.calculate_macd(symbol, day.date)

                # Update if we have values
                updated = False
                if rsi is not None:
                    day.rsi = rsi
                    updated = True

                if macd is not None:
                    day.macd = macd
                    day.macd_signal = macd_signal
                    day.macd_histogram = macd_histogram
                    updated = True

                if updated:
                    day.save(update_fields=["rsi", "macd", "macd_signal", "macd_histogram", "updated_at"])
                    records_updated += 1

            if symbols_processed % 10 == 0:
                self.stdout.write(self.style.SUCCESS(f"  Processed {symbols_processed}/{total_symbols} symbols, {records_updated} records updated"))

        self.stdout.write(self.style.SUCCESS(f"\nCompleted! {symbols_processed} symbols processed, {records_updated} records updated"))
