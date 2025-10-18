from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from zimuabull.daytrading.feature_builder import build_features_for_date
from zimuabull.models import Symbol


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        msg = f"Invalid date format '{value}'. Use YYYY-MM-DD."
        raise CommandError(msg) from exc


class Command(BaseCommand):
    help = "Generate day trading feature snapshots for symbols."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="Generate features for a specific trade date (YYYY-MM-DD).")
        parser.add_argument("--start-date", help="Backfill starting date (YYYY-MM-DD).")
        parser.add_argument("--end-date", help="Backfill ending date (YYYY-MM-DD).")
        parser.add_argument("--symbol", help="Specific symbol to process (e.g., AAPL).")
        parser.add_argument("--exchange", help="Limit to symbols from a specific exchange code.")
        parser.add_argument("--overwrite", action="store_true", help="Overwrite existing snapshots.")

    def handle(self, *args, **options):
        date_str = options.get("date")
        start_date_str = options.get("start_date")
        end_date_str = options.get("end_date")
        symbol_code = options.get("symbol")
        exchange_code = options.get("exchange")
        overwrite = options.get("overwrite")

        symbols = Symbol.objects.all()
        if exchange_code:
            symbols = symbols.filter(exchange__code=exchange_code)
        if symbol_code:
            symbols = symbols.filter(symbol=symbol_code)

        if not symbols.exists():
            msg = "No symbols found for the provided filters."
            raise CommandError(msg)

        symbol_count = symbols.count()
        self.stdout.write(f"Processing {symbol_count} symbols...")

        if date_str:
            trade_date = _parse_date(date_str)
            self.stdout.write(f"Generating features for {trade_date}...")
            processed = build_features_for_date(trade_date, symbols=symbols, overwrite=overwrite)
            self.stdout.write(self.style.SUCCESS(f"✓ Generated {processed} feature snapshots for {trade_date}"))
            return

        if start_date_str:
            start_date = _parse_date(start_date_str)
        else:
            msg = "Either --date or --start-date must be provided."
            raise CommandError(msg)

        end_date: date | None = _parse_date(end_date_str) if end_date_str else date.today()

        # Call backfill with progress callback
        self.stdout.write(f"Backfilling features from {start_date} to {end_date}...")
        processed = self._backfill_with_progress(
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            overwrite=overwrite,
        )
        self.stdout.write(self.style.SUCCESS(f"\n✓ Backfilled {processed} feature snapshots between {start_date} and {end_date}"))

    def _backfill_with_progress(self, start_date, end_date, symbols, overwrite):
        """Backfill features with progress tracking"""
        import time
        import pandas as pd
        from zimuabull.daytrading.feature_builder import build_feature_snapshot

        total_processed = 0
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")
        total_days = len([d for d in date_range if d.weekday() < 5])  # Count weekdays only

        self.stdout.write(f"Total trading days to process: {total_days}")

        start_time = time.time()
        day_count = 0

        for day in date_range:
            current_date = day.date()

            # Skip weekends
            if current_date.weekday() >= 5:
                continue

            day_count += 1
            day_processed = 0

            for symbol in symbols:
                snapshot = build_feature_snapshot(symbol, current_date, overwrite=overwrite)
                if snapshot:
                    day_processed += 1
                    total_processed += 1

            # Calculate progress metrics
            progress = (day_count / total_days) * 100
            elapsed_time = time.time() - start_time

            # Calculate speed and ETA
            if day_count > 0:
                avg_time_per_day = elapsed_time / day_count
                remaining_days = total_days - day_count
                eta_seconds = avg_time_per_day * remaining_days

                # Format speed
                speed = day_count / elapsed_time * 60  # days per minute

                # Format ETA
                if eta_seconds < 60:
                    eta_str = f"{int(eta_seconds)}s"
                elif eta_seconds < 3600:
                    eta_str = f"{int(eta_seconds / 60)}m {int(eta_seconds % 60)}s"
                else:
                    hours = int(eta_seconds / 3600)
                    minutes = int((eta_seconds % 3600) / 60)
                    eta_str = f"{hours}h {minutes}m"
            else:
                speed = 0
                eta_str = "calculating..."

            # Progress indicator with ETA
            self.stdout.write(
                f"\r[{day_count}/{total_days}] {current_date} | "
                f"Day: {day_processed} snapshots | "
                f"Total: {total_processed} | "
                f"Progress: {progress:.1f}% | "
                f"Speed: {speed:.1f} days/min | "
                f"ETA: {eta_str}",
                ending=""
            )
            self.stdout.flush()

        # Final elapsed time
        total_time = time.time() - start_time
        if total_time < 60:
            time_str = f"{total_time:.1f}s"
        elif total_time < 3600:
            time_str = f"{int(total_time / 60)}m {int(total_time % 60)}s"
        else:
            hours = int(total_time / 3600)
            minutes = int((total_time % 3600) / 60)
            time_str = f"{hours}h {minutes}m"

        self.stdout.write(f"\nCompleted in {time_str}")

        return total_processed
