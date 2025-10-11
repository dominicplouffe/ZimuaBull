from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from zimuabull.daytrading.backtest import run_backtest
from zimuabull.daytrading.dataset import load_dataset
from zimuabull.daytrading.modeling import load_model


class Command(BaseCommand):
    help = "Run a backtest of the trained intraday strategy."

    def add_arguments(self, parser):
        parser.add_argument("--start-date", help="Backtest start date (YYYY-MM-DD)")
        parser.add_argument("--end-date", help="Backtest end date (YYYY-MM-DD)")
        parser.add_argument("--bankroll", type=float, default=10000, help="Starting capital.")
        parser.add_argument("--max-positions", type=int, default=5, help="Maximum positions per day.")

    def handle(self, *args, **options):
        start_date = options.get("start_date")
        end_date = options.get("end_date")
        bankroll = options.get("bankroll")
        max_positions = options.get("max_positions")

        try:
            dataset = load_dataset(
                start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
                end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
            )
        except ValueError as exc:
            msg = f"Invalid date format: {exc}"
            raise CommandError(msg) from exc

        if dataset.features.empty:
            msg = "No dataset rows available for the selected date range."
            raise CommandError(msg)

        model, feature_columns = load_model()

        result = run_backtest(
            dataset=dataset,
            model=model,
            trained_columns=feature_columns,
            bankroll=bankroll,
            max_positions=max_positions,
        )

        summary = result.summary
        self.stdout.write(self.style.SUCCESS("Backtest Summary"))
        for key, value in summary.items():
            self.stdout.write(f"  {key}: {value}")

        self.stdout.write(self.style.SUCCESS(f"Trades executed: {len(result.trades)}"))
