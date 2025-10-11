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

        # Load dataset with progress
        self.stdout.write("📊 Loading dataset...")
        try:
            dataset = load_dataset(
                start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
                end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
            )
        except ValueError as exc:
            msg = f"Invalid date format: {exc}"
            raise CommandError(msg) from exc

        n_samples = len(dataset.features)
        n_features = len(dataset.features.columns)

        self.stdout.write(self.style.SUCCESS(f"✓ Loaded {n_samples:,} samples with {n_features} features"))

        if n_samples < min_rows:
            msg = f"Insufficient samples ({n_samples:,}). Need at least {min_rows:,}."
            raise CommandError(msg)

        # Train model with progress
        self.stdout.write("\n🔧 Training HistGradientBoostingRegressor model...")
        self.stdout.write("   • Using TimeSeriesSplit for cross-validation (prevents data leakage)")
        self.stdout.write("   • Training may take 2-10 minutes depending on dataset size...")

        model, metrics, feature_columns, imputer = train_regression_model(dataset)

        # Display metrics
        self.stdout.write(self.style.SUCCESS("\n✓ Model training complete!"))
        self.stdout.write("\n📈 Cross-Validation Metrics:")
        self.stdout.write(f"   • R² Score:  {metrics['r2_mean']:.4f} (±{metrics['r2_std']:.4f})")
        self.stdout.write(f"   • MAE Score: {metrics['mae_mean']:.4f} (±{metrics['mae_std']:.4f})")
        self.stdout.write(f"   • Samples:   {metrics['n_samples']:,}")
        self.stdout.write(f"   • Features:  {metrics['n_features']}")

        # Interpret metrics
        self.stdout.write("\n💡 Interpretation:")
        if metrics['r2_mean'] > 0.15:
            self.stdout.write(self.style.SUCCESS("   ✓ Excellent R² for intraday prediction!"))
        elif metrics['r2_mean'] > 0.08:
            self.stdout.write(self.style.SUCCESS("   ✓ Good R² for intraday prediction"))
        elif metrics['r2_mean'] > 0:
            self.stdout.write(self.style.WARNING("   ⚠ Low R² - model may underperform"))
        else:
            self.stdout.write(self.style.ERROR("   ✗ Negative R² - model is worse than mean prediction!"))

        if metrics['mae_mean'] < 0.01:
            self.stdout.write(self.style.SUCCESS("   ✓ Excellent MAE (<1% average error)"))
        elif metrics['mae_mean'] < 0.015:
            self.stdout.write(self.style.SUCCESS("   ✓ Good MAE (<1.5% average error)"))
        else:
            self.stdout.write(self.style.WARNING("   ⚠ High MAE - predictions may be inaccurate"))

        # Save model
        self.stdout.write("\n💾 Saving model...")
        save_path = save_model(model, metrics, feature_columns, imputer)

        self.stdout.write(self.style.SUCCESS(f"\n✓ Model saved to: {save_path}"))
        self.stdout.write(self.style.SUCCESS(f"✓ Model type: {metrics['model_type']}"))
        self.stdout.write(self.style.SUCCESS(f"✓ Trained at: {metrics['trained_at']}"))

        self.stdout.write("\n🎯 Next Steps:")
        self.stdout.write("   1. Run backtest: python manage.py backtest_daytrading --start-date <date> --end-date <date>")
        self.stdout.write("   2. Review backtest metrics (Sharpe > 1.0, Win Rate > 48%)")
        self.stdout.write("   3. Paper trade for 2-4 weeks before going live")
