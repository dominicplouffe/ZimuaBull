"""
Management command to recalculate trading signals for all symbols.

Usage:
    python manage.py recalculate_signals
    python manage.py recalculate_signals --exchange TSE
    python manage.py recalculate_signals --symbol AAPL --exchange NASDAQ
"""

from django.core.management.base import BaseCommand
from zimuabull.models import Symbol


class Command(BaseCommand):
    help = 'Recalculate trading signals for symbols based on latest predictions and technical indicators'

    def add_arguments(self, parser):
        parser.add_argument(
            '--exchange',
            type=str,
            help='Only recalculate signals for symbols on this exchange (e.g., TSE, NASDAQ)',
        )
        parser.add_argument(
            '--symbol',
            type=str,
            help='Only recalculate signal for this specific symbol (requires --exchange)',
        )

    def handle(self, *args, **options):
        exchange_code = options.get('exchange')
        symbol_ticker = options.get('symbol')

        # Build queryset
        queryset = Symbol.objects.all()

        if exchange_code:
            queryset = queryset.filter(exchange__code=exchange_code)
            self.stdout.write(f"Filtering by exchange: {exchange_code}")

        if symbol_ticker:
            if not exchange_code:
                self.stdout.write(
                    self.style.ERROR('--symbol requires --exchange to be specified')
                )
                return
            queryset = queryset.filter(symbol=symbol_ticker)
            self.stdout.write(f"Filtering by symbol: {symbol_ticker}")

        total_symbols = queryset.count()

        if total_symbols == 0:
            self.stdout.write(self.style.WARNING('No symbols found matching criteria'))
            return

        self.stdout.write(f"Recalculating signals for {total_symbols} symbols...")

        updated_count = 0
        error_count = 0
        signal_counts = {
            'STRONG_BUY': 0,
            'BUY': 0,
            'HOLD': 0,
            'SELL': 0,
            'STRONG_SELL': 0,
            'NA': 0
        }

        for symbol in queryset:
            try:
                old_signal = symbol.obv_status
                new_signal = symbol.update_trading_signal()

                if old_signal != new_signal:
                    self.stdout.write(
                        f"  {symbol.symbol} ({symbol.exchange.code}): {old_signal} → {new_signal}"
                    )
                    updated_count += 1

                signal_counts[new_signal] = signal_counts.get(new_signal, 0) + 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  Error processing {symbol.symbol}: {e}")
                )
                error_count += 1

        # Summary
        self.stdout.write(self.style.SUCCESS(f"\n✓ Processed {total_symbols} symbols"))
        self.stdout.write(f"  Changed: {updated_count}")
        self.stdout.write(f"  Errors: {error_count}")
        self.stdout.write("\nSignal Distribution:")
        for signal, count in signal_counts.items():
            percentage = (count / total_symbols * 100) if total_symbols > 0 else 0
            self.stdout.write(f"  {signal}: {count} ({percentage:.1f}%)")
