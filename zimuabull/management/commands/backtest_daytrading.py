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

        # Load dataset with progress
        self.stdout.write("📊 Loading backtest dataset...")
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

        n_samples = len(dataset.features)
        self.stdout.write(self.style.SUCCESS(f"✓ Loaded {n_samples:,} samples for backtesting"))

        # Load model
        self.stdout.write("\n🤖 Loading trained model...")
        model, feature_columns, imputer = load_model()
        self.stdout.write(self.style.SUCCESS("✓ Model loaded successfully"))

        # Run backtest
        self.stdout.write(f"\n🔄 Running backtest simulation...")
        self.stdout.write(f"   • Starting capital: ${bankroll:,.2f}")
        self.stdout.write(f"   • Max positions: {max_positions}")
        self.stdout.write(f"   • Transaction cost: 0.05% + commission")
        self.stdout.write(f"   • Processing...")

        result = run_backtest(
            dataset=dataset,
            model=model,
            trained_columns=feature_columns,
            imputer=imputer,
            bankroll=bankroll,
            max_positions=max_positions,
        )

        summary = result.summary

        # Display results with formatting and interpretation
        self.stdout.write(self.style.SUCCESS("\n✓ Backtest complete!"))
        self.stdout.write("\n" + "="*60)
        self.stdout.write("📈 BACKTEST RESULTS")
        self.stdout.write("="*60)

        # Capital metrics
        self.stdout.write(f"\n💰 Capital:")
        self.stdout.write(f"   Starting:  ${summary['starting_capital']:>12,.2f}")
        self.stdout.write(f"   Ending:    ${summary['ending_capital']:>12,.2f}")
        profit = summary['ending_capital'] - summary['starting_capital']
        profit_color = self.style.SUCCESS if profit > 0 else self.style.ERROR
        self.stdout.write(profit_color(f"   Profit:    ${profit:>12,.2f}"))

        # Performance metrics
        self.stdout.write(f"\n📊 Returns:")
        return_pct = summary['total_return'] * 100
        return_color = self.style.SUCCESS if return_pct > 0 else self.style.ERROR
        self.stdout.write(return_color(f"   Total Return:      {return_pct:>8.2f}%"))

        annual_pct = summary['annualized_return'] * 100
        annual_color = self.style.SUCCESS if annual_pct > 15 else self.style.WARNING if annual_pct > 5 else self.style.ERROR
        self.stdout.write(annual_color(f"   Annualized Return: {annual_pct:>8.2f}%"))

        # Risk metrics
        self.stdout.write(f"\n⚠️  Risk:")
        drawdown_pct = summary['max_drawdown'] * 100
        dd_color = self.style.SUCCESS if drawdown_pct < 15 else self.style.WARNING if drawdown_pct < 25 else self.style.ERROR
        self.stdout.write(dd_color(f"   Max Drawdown:      {drawdown_pct:>8.2f}%"))

        sharpe = summary['sharpe']
        sharpe_color = self.style.SUCCESS if sharpe > 1.2 else self.style.WARNING if sharpe > 0.8 else self.style.ERROR
        self.stdout.write(sharpe_color(f"   Sharpe Ratio:      {sharpe:>8.2f}"))

        # Trading metrics
        self.stdout.write(f"\n🎯 Trading:")
        win_rate_pct = summary['win_rate'] * 100
        wr_color = self.style.SUCCESS if win_rate_pct > 52 else self.style.WARNING if win_rate_pct > 48 else self.style.ERROR
        self.stdout.write(wr_color(f"   Win Rate:          {win_rate_pct:>8.2f}%"))
        self.stdout.write(f"   Total Trades:      {summary['trades']:>8,}")

        # Interpretation
        self.stdout.write("\n" + "="*60)
        self.stdout.write("💡 INTERPRETATION")
        self.stdout.write("="*60)

        # Overall assessment
        if annual_pct > 20 and sharpe > 1.5 and win_rate_pct > 52:
            self.stdout.write(self.style.SUCCESS("\n🎉 EXCELLENT PERFORMANCE!"))
            self.stdout.write("   ✓ All metrics exceed targets")
            self.stdout.write("   ✓ Model is ready for paper trading")
        elif annual_pct > 10 and sharpe > 1.0 and win_rate_pct > 48:
            self.stdout.write(self.style.SUCCESS("\n✓ GOOD PERFORMANCE"))
            self.stdout.write("   ✓ Metrics are acceptable")
            self.stdout.write("   ⚠ Consider paper trading to validate")
        elif annual_pct > 0 and sharpe > 0.5:
            self.stdout.write(self.style.WARNING("\n⚠ MARGINAL PERFORMANCE"))
            self.stdout.write("   ⚠ Metrics are below targets")
            self.stdout.write("   ⚠ Needs improvement before live trading")
        else:
            self.stdout.write(self.style.ERROR("\n✗ POOR PERFORMANCE"))
            self.stdout.write("   ✗ Model is not profitable")
            self.stdout.write("   ✗ Do NOT use for live trading")

        # Metric targets
        self.stdout.write("\n📋 Target Metrics:")
        self.stdout.write(f"   Annualized Return: >15% (yours: {annual_pct:.2f}%)")
        self.stdout.write(f"   Sharpe Ratio:      >1.2  (yours: {sharpe:.2f})")
        self.stdout.write(f"   Win Rate:          >50%  (yours: {win_rate_pct:.1f}%)")
        self.stdout.write(f"   Max Drawdown:      <20%  (yours: {drawdown_pct:.1f}%)")

        self.stdout.write("\n" + "="*60)

        # Next steps
        if annual_pct > 15 and sharpe > 1.2 and win_rate_pct > 50:
            self.stdout.write("\n🎯 Next Steps:")
            self.stdout.write("   1. ✓ Backtest looks good!")
            self.stdout.write("   2. Start paper trading for 2-4 weeks")
            self.stdout.write("   3. Monitor daily: Win rate, Sharpe, Drawdown")
            self.stdout.write("   4. Go live only if paper trading confirms backtest")
        else:
            self.stdout.write("\n🎯 Recommended Actions:")
            self.stdout.write("   1. Review feature engineering (add more features)")
            self.stdout.write("   2. Try longer training period (more data)")
            self.stdout.write("   3. Consider hyperparameter tuning")
            self.stdout.write("   4. Re-run backtest after improvements")
