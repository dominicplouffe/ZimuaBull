from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from zimuabull.daytrading.feature_builder import backfill_features, build_features_for_date
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

        if date_str:
            trade_date = _parse_date(date_str)
            processed = build_features_for_date(trade_date, symbols=symbols, overwrite=overwrite)
            self.stdout.write(self.style.SUCCESS(f"Generated {processed} feature snapshots for {trade_date}"))
            return

        if start_date_str:
            start_date = _parse_date(start_date_str)
        else:
            msg = "Either --date or --start-date must be provided."
            raise CommandError(msg)

        end_date: date | None = _parse_date(end_date_str) if end_date_str else date.today()

        processed = backfill_features(
            start_date=start_date,
            end_date=end_date,
            symbols=symbols,
            overwrite=overwrite,
        )
        self.stdout.write(self.style.SUCCESS(f"Backfilled {processed} feature snapshots between {start_date} and {end_date}"))
