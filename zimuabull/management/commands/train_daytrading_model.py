from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from zimuabull.daytrading.dataset import load_dataset
from zimuabull.daytrading.modeling import save_model, train_regression_model


class Command(BaseCommand):
    help = "Train the intraday day-trading model using FeatureSnapshot data."

    def add_arguments(self, parser):
        parser.add_argument("--start-date", help="Training start date (YYYY-MM-DD)")
        parser.add_argument("--end-date", help="Training end date (YYYY-MM-DD)")
        parser.add_argument("--min-rows", type=int, default=500, help="Minimum rows required to train.")

    def handle(self, *args, **options):
        start_date = options.get("start_date")
        end_date = options.get("end_date")
        min_rows = options.get("min_rows")

        try:
            dataset = load_dataset(
                start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
                end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
            )
        except ValueError as exc:
            msg = f"Invalid date format: {exc}"
            raise CommandError(msg) from exc

        if len(dataset.features) < min_rows:
            msg = f"Insufficient samples ({len(dataset.features)}). Need at least {min_rows}."
            raise CommandError(msg)

        model, metrics, feature_columns = train_regression_model(dataset)
        save_path = save_model(model, metrics, feature_columns)

        self.stdout.write(self.style.SUCCESS(f"Model trained and saved to {save_path}"))
        self.stdout.write(self.style.SUCCESS(f"Training metrics: {metrics}"))
