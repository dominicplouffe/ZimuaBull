"""
Automated Day Trading Model Retraining Command

This command handles the complete retraining pipeline:
1. Detects last feature snapshot date
2. Generates missing features from that date to today
3. Updates labels for completed trading days
4. Calculates technical indicators if needed
5. Trains new model
6. Runs backtest validation
7. Optionally bumps feature version

Usage:
    # Standard retraining (incremental)
    python manage.py retrain_daytrading_model

    # Force regenerate all features (last 90 days)
    python manage.py retrain_daytrading_model --full-rebuild

    # Bump version and retrain from scratch
    python manage.py retrain_daytrading_model --bump-version

    # Custom parameters
    python manage.py retrain_daytrading_model --exchange NASDAQ --training-days 120
"""

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from zimuabull.daytrading.backtest import run_backtest
from zimuabull.daytrading.constants import (
    FEATURE_VERSION,
    MIN_TRAINING_ROWS,
    MODEL_DIR,
    MODEL_METADATA_FILENAME,
)
from zimuabull.daytrading.dataset import load_dataset
from zimuabull.daytrading.feature_builder import (
    build_feature_snapshot,
    update_labels_for_date,
)
from zimuabull.daytrading.modeling import save_model, train_regression_model
from zimuabull.models import DaySymbol, FeatureSnapshot, ModelVersion, Symbol


class Command(BaseCommand):
    help = "Automated day trading model retraining pipeline"

    def add_arguments(self, parser):
        parser.add_argument(
            "--exchange",
            type=str,
            default=None,
            help="Exchange to process (default: all exchanges). Use 'NASDAQ', 'NYSE', 'TSE', etc. or leave blank for all.",
        )
        parser.add_argument(
            "--training-days",
            type=int,
            default=90,
            help="Number of days of historical data for training (default: 90)",
        )
        parser.add_argument(
            "--backtest-days",
            type=int,
            default=30,
            help="Number of days for backtest validation (default: 30)",
        )
        parser.add_argument(
            "--full-rebuild",
            action="store_true",
            help="Regenerate all features from scratch (last N training days)",
        )
        parser.add_argument(
            "--bump-version",
            action="store_true",
            help="Bump feature version (v2 -> v3) and rebuild everything",
        )
        parser.add_argument(
            "--skip-indicators",
            action="store_true",
            help="Skip technical indicator calculation (assume already done)",
        )
        parser.add_argument(
            "--skip-backtest",
            action="store_true",
            help="Skip backtest validation",
        )
        parser.add_argument(
            "--min-rows",
            type=int,
            default=MIN_TRAINING_ROWS,
            help=f"Minimum training samples required (default: {MIN_TRAINING_ROWS})",
        )

    def handle(self, *args, **options):
        self.options = options
        exchange = options["exchange"]
        training_days = options["training_days"]
        backtest_days = options["backtest_days"]
        full_rebuild = options["full_rebuild"]
        bump_version = options["bump_version"]
        skip_indicators = options["skip_indicators"]
        skip_backtest = options["skip_backtest"]
        min_rows = options["min_rows"]

        self.stdout.write("=" * 80)
        self.stdout.write("🤖 AUTOMATED DAY TRADING MODEL RETRAINING")
        self.stdout.write("=" * 80)
        self.stdout.write(f"\nExchange: {exchange if exchange else 'ALL'}")
        self.stdout.write(f"Training window: {training_days} days")
        self.stdout.write(f"Backtest window: {backtest_days} days")
        self.stdout.write(f"Current feature version: {FEATURE_VERSION}")

        # Step 0: Handle version bump if requested
        new_version = FEATURE_VERSION
        if bump_version:
            new_version = self._bump_version()
            self.stdout.write(f"\n✓ Bumped version: {FEATURE_VERSION} → {new_version}")
            full_rebuild = True  # Force full rebuild with new version

        # Step 1: Verify prerequisites
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("📋 STEP 1: VERIFYING PREREQUISITES")
        self.stdout.write("=" * 80)
        self._verify_prerequisites(exchange)

        # Step 2: Calculate technical indicators if needed
        if not skip_indicators:
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write("📊 STEP 2: CALCULATING TECHNICAL INDICATORS")
            self.stdout.write("=" * 80)
            self._calculate_indicators(exchange)

        # Step 3: Determine date range for feature generation
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("📅 STEP 3: DETERMINING FEATURE GENERATION RANGE")
        self.stdout.write("=" * 80)
        start_date, end_date = self._determine_date_range(
            exchange, training_days, full_rebuild, new_version
        )

        # Step 4: Generate features
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("🔧 STEP 4: GENERATING FEATURES")
        self.stdout.write("=" * 80)
        self._generate_features(exchange, start_date, end_date, new_version)

        # Step 5: Update labels
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("🏷️  STEP 5: UPDATING LABELS")
        self.stdout.write("=" * 80)
        self._update_labels(start_date, end_date, new_version)

        # Record currently deployed model (if not already captured) before training a new one
        self._upsert_existing_model_version(feature_version=FEATURE_VERSION)

        # Step 6: Train model
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("🤖 STEP 6: TRAINING MODEL")
        self.stdout.write("=" * 80)
        training_start = end_date - timedelta(days=training_days)
        model, metrics, feature_columns, imputer, model_path = self._train_model(
            training_start, end_date, min_rows, new_version
        )

        model_version = self._record_model_version(
            feature_version=new_version,
            metrics=metrics,
            model_path=model_path,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Recorded model version {model_version.version} ({model_version.feature_version})"
            )
        )

        # Step 7: Run backtest
        if not skip_backtest:
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write("📈 STEP 7: RUNNING BACKTEST VALIDATION")
            self.stdout.write("=" * 80)
            backtest_start = end_date - timedelta(days=backtest_days)
            self._run_backtest(
                model,
                feature_columns,
                imputer,
                backtest_start,
                end_date,
                new_version,
            )

        # Step 8: Summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("✅ RETRAINING COMPLETE!")
        self.stdout.write("=" * 80)
        self._print_summary(metrics, new_version)

    def _verify_prerequisites(self, exchange):
        """Verify that we have necessary data"""
        # Check symbols
        if exchange:
            symbols = Symbol.objects.filter(exchange__code=exchange)
            symbol_count = symbols.count()

            if symbol_count == 0:
                raise CommandError(f"No symbols found for exchange '{exchange}'")

            self.stdout.write(f"✓ Found {symbol_count:,} symbols for {exchange}")
        else:
            # All exchanges
            symbols = Symbol.objects.all()
            symbol_count = symbols.count()

            if symbol_count == 0:
                raise CommandError("No symbols found in database")

            # Show breakdown by exchange
            from django.db.models import Count
            exchanges = Symbol.objects.values('exchange__code').annotate(count=Count('id')).order_by('-count')
            self.stdout.write(f"✓ Found {symbol_count:,} symbols across {len(exchanges)} exchanges:")
            for ex in exchanges:
                self.stdout.write(f"    - {ex['exchange__code']}: {ex['count']:,} symbols")

        # Check DaySymbol data
        recent_date = date.today() - timedelta(days=7)
        if exchange:
            recent_days = DaySymbol.objects.filter(
                symbol__exchange__code=exchange, date__gte=recent_date
            ).count()

            if recent_days == 0:
                raise CommandError(
                    f"No recent DaySymbol data for {exchange}. "
                    f"Please run data collection first."
                )

            self.stdout.write(f"✓ Found {recent_days:,} recent DaySymbol records (last 7 days)")

            # Check technical indicators
            days_with_rsi = DaySymbol.objects.filter(
                symbol__exchange__code=exchange, date__gte=recent_date, rsi__isnull=False
            ).count()
        else:
            recent_days = DaySymbol.objects.filter(date__gte=recent_date).count()

            if recent_days == 0:
                raise CommandError(
                    "No recent DaySymbol data. Please run data collection first."
                )

            self.stdout.write(f"✓ Found {recent_days:,} recent DaySymbol records (last 7 days)")

            # Check technical indicators
            days_with_rsi = DaySymbol.objects.filter(
                date__gte=recent_date, rsi__isnull=False
            ).count()

        rsi_pct = (days_with_rsi / recent_days * 100) if recent_days > 0 else 0

        self.stdout.write(
            f"✓ Technical indicators: {days_with_rsi:,}/{recent_days:,} ({rsi_pct:.1f}%) with RSI"
        )

        if rsi_pct < 50:
            self.stdout.write(
                self.style.WARNING(
                    "   ⚠ Low RSI coverage - will calculate indicators"
                )
            )

    def _calculate_indicators(self, exchange):
        """Calculate RSI and MACD for symbols missing them"""
        from zimuabull.models import DaySymbol, Symbol

        if exchange:
            self.stdout.write(f"Calculating technical indicators for {exchange}...")
            symbols = Symbol.objects.filter(exchange__code=exchange)
        else:
            self.stdout.write("Calculating technical indicators for all exchanges...")
            symbols = Symbol.objects.all()

        total_updated = 0
        symbols_processed = 0

        for symbol in symbols:
            # Get days without RSI
            days = DaySymbol.objects.filter(
                symbol=symbol, rsi__isnull=True
            ).order_by("date")

            if not days.exists():
                continue

            symbols_processed += 1

            for day in days:
                # Calculate RSI
                rsi = DaySymbol.calculate_rsi(symbol, day.date, period=14)

                # Calculate MACD
                macd, macd_signal, macd_histogram = DaySymbol.calculate_macd(
                    symbol, day.date
                )

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
                    day.save(
                        update_fields=[
                            "rsi",
                            "macd",
                            "macd_signal",
                            "macd_histogram",
                            "updated_at",
                        ]
                    )
                    total_updated += 1

            if symbols_processed % 50 == 0:
                self.stdout.write(
                    f"   Processed {symbols_processed}/{symbols.count()} symbols, "
                    f"{total_updated} records updated"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Updated {total_updated} records across {symbols_processed} symbols"
            )
        )

    def _determine_date_range(self, exchange, training_days, full_rebuild, version):
        """Determine the date range for feature generation"""
        end_date = date.today()

        # Skip weekends
        while end_date.weekday() >= 5:
            end_date -= timedelta(days=1)

        if full_rebuild:
            # Rebuild from scratch
            start_date = end_date - timedelta(days=training_days)
            self.stdout.write(
                f"Full rebuild mode: Regenerating features from {start_date} to {end_date}"
            )
        else:
            # Find last feature snapshot date
            if exchange:
                last_snapshot = (
                    FeatureSnapshot.objects.filter(
                        symbol__exchange__code=exchange, feature_version=version
                    )
                    .order_by("-trade_date")
                    .first()
                )
            else:
                last_snapshot = (
                    FeatureSnapshot.objects.filter(feature_version=version)
                    .order_by("-trade_date")
                    .first()
                )

            if last_snapshot:
                # Start from day after last snapshot
                start_date = last_snapshot.trade_date + timedelta(days=1)
                self.stdout.write(
                    f"Incremental mode: Last snapshot found for {last_snapshot.trade_date}"
                )
                self.stdout.write(
                    f"Will generate features from {start_date} to {end_date}"
                )

                # But ensure we have at least training_days of data
                min_start = end_date - timedelta(days=training_days)
                if start_date > min_start:
                    # Not enough historical data, extend range
                    self.stdout.write(
                        self.style.WARNING(
                            f"   ⚠ Need more history for training. "
                            f"Extending start date to {min_start}"
                        )
                    )
                    start_date = min_start
            else:
                # No snapshots found, start from scratch
                start_date = end_date - timedelta(days=training_days)
                self.stdout.write(
                    f"No snapshots found. Starting from {start_date}"
                )

        # Skip too far in the past
        if exchange:
            earliest_data = (
                DaySymbol.objects.filter(symbol__exchange__code=exchange)
                .order_by("date")
                .first()
            )
        else:
            earliest_data = DaySymbol.objects.order_by("date").first()

        if earliest_data and start_date < earliest_data.date:
            start_date = earliest_data.date
            self.stdout.write(
                f"Adjusted start date to earliest available data: {start_date}"
            )

        return start_date, end_date

    def _generate_features(self, exchange, start_date, end_date, version):
        """Generate feature snapshots for date range"""
        import time

        if exchange:
            symbols = Symbol.objects.filter(exchange__code=exchange)
            symbol_count = symbols.count()
            self.stdout.write(
                f"Generating features for {symbol_count} {exchange} symbols "
                f"from {start_date} to {end_date}..."
            )
        else:
            symbols = Symbol.objects.all()
            symbol_count = symbols.count()
            self.stdout.write(
                f"Generating features for {symbol_count} symbols (all exchanges) "
                f"from {start_date} to {end_date}..."
            )

        # Generate date range (skip weekends)
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")
        trading_days = [d.date() for d in date_range if d.weekday() < 5]

        total_days = len(trading_days)
        self.stdout.write(f"Total trading days to process: {total_days}")

        total_processed = 0
        start_time = time.time()

        for day_idx, current_date in enumerate(trading_days, 1):
            day_processed = 0

            for symbol in symbols:
                snapshot = build_feature_snapshot(
                    symbol, current_date, overwrite=self.options["full_rebuild"]
                )
                if snapshot:
                    day_processed += 1
                    total_processed += 1

            # Progress indicator
            progress = (day_idx / total_days) * 100
            elapsed = time.time() - start_time
            speed = day_idx / elapsed * 60 if elapsed > 0 else 0
            eta_seconds = (
                (total_days - day_idx) / speed * 60 if speed > 0 else 0
            )

            eta_str = self._format_time(eta_seconds)

            self.stdout.write(
                f"\r[{day_idx}/{total_days}] {current_date} | "
                f"Day: {day_processed} snapshots | "
                f"Total: {total_processed:,} | "
                f"Progress: {progress:.1f}% | "
                f"Speed: {speed:.1f} days/min | "
                f"ETA: {eta_str}",
                ending="",
            )
            self.stdout.flush()

        elapsed_time = time.time() - start_time
        self.stdout.write(
            f"\n✓ Generated {total_processed:,} feature snapshots "
            f"in {self._format_time(elapsed_time)}"
        )

    def _update_labels(self, start_date, end_date, version):
        """Update labels for completed trading days"""
        self.stdout.write(
            f"Updating labels from {start_date} to {end_date - timedelta(days=1)}..."
        )

        # Can only label up to yesterday (need today's close price)
        yesterday = date.today() - timedelta(days=1)
        label_end = min(end_date - timedelta(days=1), yesterday)

        date_range = pd.date_range(start=start_date, end=label_end, freq="D")
        trading_days = [d.date() for d in date_range if d.weekday() < 5]

        total_updated = 0

        for current_date in trading_days:
            updated = update_labels_for_date(current_date, symbols=None)
            total_updated += updated

            if total_updated % 100 == 0:
                self.stdout.write(
                    f"   {current_date}: Updated {updated} labels (total: {total_updated:,})"
                )

        self.stdout.write(
            self.style.SUCCESS(f"✓ Updated {total_updated:,} labels")
        )

        # Check label coverage
        labeled = FeatureSnapshot.objects.filter(
            feature_version=version,
            trade_date__gte=start_date,
            trade_date__lte=label_end,
            label_ready=True,
        ).count()

        total = FeatureSnapshot.objects.filter(
            feature_version=version,
            trade_date__gte=start_date,
            trade_date__lte=label_end,
        ).count()

        label_pct = (labeled / total * 100) if total > 0 else 0
        self.stdout.write(
            f"✓ Label coverage: {labeled:,}/{total:,} ({label_pct:.1f}%)"
        )

    def _train_model(self, start_date, end_date, min_rows, version):
        """Train the regression model"""
        self.stdout.write(f"Loading dataset from {start_date} to {end_date}...")

        dataset = load_dataset(
            start_date=start_date, end_date=end_date, feature_version=version
        )

        n_samples = len(dataset.features)
        n_features = len(dataset.features.columns)

        self.stdout.write(
            f"✓ Loaded {n_samples:,} samples with {n_features} features"
        )

        if n_samples < min_rows:
            raise CommandError(
                f"Insufficient training samples: {n_samples:,} < {min_rows:,}\n"
                f"Extend the date range or collect more data."
            )

        # Train model
        self.stdout.write("\nTraining HistGradientBoostingRegressor...")
        self.stdout.write(
            "   • Using TimeSeriesSplit cross-validation (prevents data leakage)"
        )
        self.stdout.write(
            "   • This may take 2-10 minutes depending on dataset size..."
        )

        model, metrics, feature_columns, imputer = train_regression_model(dataset)

        # Display metrics
        self.stdout.write(self.style.SUCCESS("\n✓ Training complete!"))
        self.stdout.write("\n📈 Cross-Validation Metrics:")
        self.stdout.write(
            f"   • R² Score:  {metrics['r2_mean']:.4f} (±{metrics['r2_std']:.4f})"
        )
        self.stdout.write(
            f"   • MAE Score: {metrics['mae_mean']:.4f} (±{metrics['mae_std']:.4f})"
        )
        self.stdout.write(f"   • Samples:   {metrics['n_samples']:,}")
        self.stdout.write(f"   • Features:  {metrics['n_features']}")

        # Interpretation
        self._interpret_training_metrics(metrics)

        # Save model
        self.stdout.write("\n💾 Saving model...")
        save_path = save_model(model, metrics, feature_columns, imputer)
        self.stdout.write(self.style.SUCCESS(f"✓ Model saved to: {save_path}"))

        return model, metrics, feature_columns, imputer, save_path

    def _run_backtest(
        self, model, feature_columns, imputer, start_date, end_date, version
    ):
        """Run backtest validation"""
        self.stdout.write(f"Loading backtest dataset from {start_date} to {end_date}...")

        dataset = load_dataset(
            start_date=start_date, end_date=end_date, feature_version=version
        )

        if dataset.features.empty:
            self.stdout.write(
                self.style.WARNING(
                    "⚠ No data for backtest period. Skipping backtest."
                )
            )
            return

        n_samples = len(dataset.features)
        self.stdout.write(f"✓ Loaded {n_samples:,} samples for backtesting")

        # Run backtest
        self.stdout.write("\nRunning backtest simulation...")
        result = run_backtest(
            dataset=dataset,
            model=model,
            trained_columns=feature_columns,
            imputer=imputer,
            bankroll=10000,
            max_positions=5,
        )

        summary = result.summary

        # Display results
        self.stdout.write(self.style.SUCCESS("\n✓ Backtest complete!"))
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("📈 BACKTEST RESULTS")
        self.stdout.write("=" * 60)

        # Capital
        self.stdout.write(f"\n💰 Capital:")
        self.stdout.write(f"   Starting:  ${summary['starting_capital']:>12,.2f}")
        self.stdout.write(f"   Ending:    ${summary['ending_capital']:>12,.2f}")
        profit = summary["ending_capital"] - summary["starting_capital"]
        profit_color = self.style.SUCCESS if profit > 0 else self.style.ERROR
        self.stdout.write(profit_color(f"   Profit:    ${profit:>12,.2f}"))

        # Returns
        self.stdout.write(f"\n📊 Returns:")
        return_pct = summary["total_return"] * 100
        return_color = self.style.SUCCESS if return_pct > 0 else self.style.ERROR
        self.stdout.write(
            return_color(f"   Total Return:      {return_pct:>8.2f}%")
        )

        annual_pct = summary["annualized_return"] * 100
        annual_color = (
            self.style.SUCCESS
            if annual_pct > 15
            else self.style.WARNING
            if annual_pct > 5
            else self.style.ERROR
        )
        self.stdout.write(
            annual_color(f"   Annualized Return: {annual_pct:>8.2f}%")
        )

        # Risk
        self.stdout.write(f"\n⚠️  Risk:")
        drawdown_pct = summary["max_drawdown"] * 100
        dd_color = (
            self.style.SUCCESS
            if drawdown_pct < 15
            else self.style.WARNING
            if drawdown_pct < 25
            else self.style.ERROR
        )
        self.stdout.write(dd_color(f"   Max Drawdown:      {drawdown_pct:>8.2f}%"))

        sharpe = summary["sharpe"]
        sharpe_color = (
            self.style.SUCCESS
            if sharpe > 1.2
            else self.style.WARNING
            if sharpe > 0.8
            else self.style.ERROR
        )
        self.stdout.write(sharpe_color(f"   Sharpe Ratio:      {sharpe:>8.2f}"))

        # Trading
        self.stdout.write(f"\n🎯 Trading:")
        win_rate_pct = summary["win_rate"] * 100
        wr_color = (
            self.style.SUCCESS
            if win_rate_pct > 52
            else self.style.WARNING
            if win_rate_pct > 48
            else self.style.ERROR
        )
        self.stdout.write(wr_color(f"   Win Rate:          {win_rate_pct:>8.2f}%"))
        self.stdout.write(f"   Total Trades:      {summary['trades']:>8,}")

        self.stdout.write("=" * 60)

        # Overall assessment
        if annual_pct > 20 and sharpe > 1.5 and win_rate_pct > 52:
            self.stdout.write(self.style.SUCCESS("\n🎉 EXCELLENT BACKTEST!"))
        elif annual_pct > 10 and sharpe > 1.0 and win_rate_pct > 48:
            self.stdout.write(self.style.SUCCESS("\n✓ GOOD BACKTEST"))
        elif annual_pct > 0 and sharpe > 0.5:
            self.stdout.write(self.style.WARNING("\n⚠ MARGINAL BACKTEST"))
        else:
            self.stdout.write(self.style.ERROR("\n✗ POOR BACKTEST"))
            self.stdout.write(
                self.style.ERROR("   Model may need improvement before deployment")
            )

    def _interpret_training_metrics(self, metrics):
        """Interpret and display training metric quality"""
        self.stdout.write("\n💡 Interpretation:")

        r2 = metrics["r2_mean"]
        if r2 > 0.15:
            self.stdout.write(
                self.style.SUCCESS(
                    "   ✓ Excellent R² for intraday prediction!"
                )
            )
        elif r2 > 0.08:
            self.stdout.write(
                self.style.SUCCESS("   ✓ Good R² for intraday prediction")
            )
        elif r2 > 0:
            self.stdout.write(
                self.style.WARNING("   ⚠ Low R² - model may underperform")
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    "   ✗ Negative R² - model is worse than mean prediction!"
                )
            )

        mae = metrics["mae_mean"]
        if mae < 0.01:
            self.stdout.write(
                self.style.SUCCESS("   ✓ Excellent MAE (<1% average error)")
            )
        elif mae < 0.015:
            self.stdout.write(
                self.style.SUCCESS("   ✓ Good MAE (<1.5% average error)")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "   ⚠ High MAE - predictions may be inaccurate"
                )
            )

    def _upsert_existing_model_version(self, feature_version: str) -> None:
        """Capture metadata for the currently deployed model before retraining."""
        model_path = MODEL_DIR / MODEL_FILENAME
        meta_path = MODEL_DIR / MODEL_METADATA_FILENAME

        if not model_path.exists() or not meta_path.exists():
            self.stdout.write(
                self.style.WARNING("⚠ Current model artifacts not found; skipping version snapshot.")
            )
            return

        if ModelVersion.objects.filter(model_file=str(model_path)).exists():
            # Version already recorded
            return

        try:
            with open(meta_path) as fp:
                metadata = json.load(fp)
        except (OSError, json.JSONDecodeError) as exc:
            self.stdout.write(
                self.style.WARNING(f"⚠ Unable to read existing model metadata ({exc}); skipping snapshot.")
            )
            return

        metrics = metadata.get("metrics", {})
        if not metrics:
            self.stdout.write(
                self.style.WARNING("⚠ Existing model metadata missing metrics; skipping snapshot.")
            )
            return

        model_version = self._create_model_version_record(
            feature_version=feature_version,
            metrics=metrics,
            model_path=model_path,
            is_active=True,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Recorded current model as version {model_version.version} before retraining"
            )
        )

    def _create_model_version_record(
        self,
        feature_version: str,
        metrics: dict,
        model_path: Path,
        *,
        is_active: bool,
    ) -> ModelVersion:
        """Persist a model version row with shared logic."""
        version_label = self._next_model_version_label(feature_version)

        trained_at = timezone.now()
        trained_at_str = metrics.get("trained_at")
        if trained_at_str:
            try:
                parsed = datetime.fromisoformat(trained_at_str)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                trained_at = parsed
            except ValueError:
                trained_at = timezone.now()

        model_version = ModelVersion.objects.create(
            version=version_label,
            model_file=str(model_path),
            feature_version=feature_version,
            trained_at=trained_at,
            training_samples=int(metrics.get("n_samples", 0)),
            cv_r2_mean=float(metrics.get("r2_mean", 0.0)),
            cv_mae_mean=float(metrics.get("mae_mean", 0.0)),
            is_active=is_active,
        )

        if is_active:
            ModelVersion.objects.exclude(pk=model_version.pk).filter(is_active=True).update(is_active=False)

        return model_version

    def _record_model_version(self, feature_version, metrics, model_path: Path) -> ModelVersion:
        """Persist model metadata for version tracking."""
        return self._create_model_version_record(
            feature_version=feature_version,
            metrics=metrics,
            model_path=model_path,
            is_active=False,
        )

    def _next_model_version_label(self, feature_version: str) -> str:
        """Generate incremental version label (e.g., v2.1, v2.2)."""
        existing_count = ModelVersion.objects.filter(feature_version=feature_version).count()
        suffix = existing_count + 1
        return f"{feature_version}.{suffix}"

    def _print_summary(self, metrics, version):
        """Print final summary"""
        # Load metadata if available
        meta_path = MODEL_DIR / MODEL_METADATA_FILENAME
        if meta_path.exists():
            with open(meta_path) as f:
                metadata = json.load(f)
            trained_at = metadata.get("metrics", {}).get("trained_at", "Unknown")
        else:
            trained_at = metrics.get("trained_at", "Unknown")

        self.stdout.write(f"\n📝 Summary:")
        self.stdout.write(f"   • Feature Version: {version}")
        self.stdout.write(f"   • Training Samples: {metrics['n_samples']:,}")
        self.stdout.write(f"   • Features: {metrics['n_features']}")
        self.stdout.write(
            f"   • R² Score: {metrics['r2_mean']:.4f} (±{metrics['r2_std']:.4f})"
        )
        self.stdout.write(
            f"   • MAE Score: {metrics['mae_mean']:.4f} (±{metrics['mae_std']:.4f})"
        )
        self.stdout.write(f"   • Trained At: {trained_at}")

        self.stdout.write("\n🎯 Next Steps:")
        self.stdout.write("   1. Review backtest results above")
        self.stdout.write("   2. If metrics look good, model is ready for paper trading")
        self.stdout.write(
            "   3. Monitor performance for 2-4 weeks before going live"
        )
        self.stdout.write("   4. Retrain weekly to keep model fresh")

        self.stdout.write(
            "\n" + self.style.SUCCESS("✅ Automated retraining pipeline complete!")
        )

    def _bump_version(self):
        """Bump feature version (e.g., v2 -> v3)"""
        from zimuabull.daytrading import constants

        current = FEATURE_VERSION
        match = re.match(r"v(\d+)", current)

        if not match:
            raise CommandError(f"Cannot parse version: {current}")

        version_num = int(match.group(1))
        new_version = f"v{version_num + 1}"

        # Update constants.py
        constants_path = Path(__file__).parent.parent.parent / "daytrading" / "constants.py"

        with open(constants_path) as f:
            content = f.read()

        # Update FEATURE_VERSION
        content = re.sub(
            r'FEATURE_VERSION = "[^"]+"',
            f'FEATURE_VERSION = "{new_version}"',
            content,
        )

        # Update MODEL_FILENAME
        content = re.sub(
            r'MODEL_FILENAME = "intraday_model_v\d+\.joblib"',
            f'MODEL_FILENAME = "intraday_model_{new_version}.joblib"',
            content,
        )

        # Update MODEL_METADATA_FILENAME
        content = re.sub(
            r'MODEL_METADATA_FILENAME = "intraday_model_v\d+_meta\.json"',
            f'MODEL_METADATA_FILENAME = "intraday_model_{new_version}_meta.json"',
            content,
        )

        # Update version history comment
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        version_comment = (
            f"# - {new_version}: Automated retrain ({today})\n"
            f'FEATURE_VERSION = "{new_version}"'
        )
        content = re.sub(
            r'FEATURE_VERSION = "[^"]+"', version_comment, content, count=1
        )

        # Write back
        with open(constants_path, "w") as f:
            f.write(content)

        # Reload the module to pick up new version
        import importlib

        importlib.reload(constants)

        return new_version

    @staticmethod
    def _format_time(seconds):
        """Format seconds to human-readable time"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m {int(seconds % 60)}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
