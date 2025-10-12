# Day Trading Algorithm - Retraining & Testing Guide

## 🎯 Overview

This guide provides step-by-step instructions for retraining and testing the improved day trading prediction algorithm.

---

## 📋 What Was Fixed

### ✅ Immediate Fixes (COMPLETED)
1. **Critical Data Leakage Fixed** - Imputation now happens separately for train/test splits
2. **Unused Variables Removed** - Cleaned up dead code in trading_engine.py
3. **Syntax Error Fixed** - Fixed dictionary formatting in close_all_positions()
4. **Transaction Costs Added** - Implemented tiered commission structure + slippage
5. **Market Hours Check Added** - Position monitoring only runs during market hours

### ✅ Short-Term Improvements (COMPLETED)
6. **Upgraded to HistGradientBoostingRegressor** - Better model with:
   - 500 trees (vs 300)
   - Max depth 6 (vs 3)
   - Early stopping
   - L2 regularization
7. **Improved Confidence Scoring** - Sigmoid-scaled Sharpe ratio (0-100 range)
8. **Better Stop/Target Calculation** - 2 ATR stops, enforced 1.5:1 reward:risk ratio
9. **Feature Importance Analysis** - Added framework (requires separate permutation testing)

---

## 🔄 STEP-BY-STEP: Retrain the Model

### Step 1: Generate Feature Snapshots

First, ensure you have feature snapshots for your training period:

```bash
# Generate features for a date range (example: last 6 months)
.venv/bin/python manage.py generate_daytrading_features \
    --start-date 2024-04-01 \
    --end-date 2024-10-11 \
    --overwrite
```

**What this does:**
- Computes 30+ technical features for each symbol/date
- Stores in `FeatureSnapshot` table
- Uses `--overwrite` to refresh existing snapshots

**Expected output:**
```
Processing features for 2024-04-01...
Processed 150 symbols
Processing features for 2024-04-02...
...
Total snapshots created: 25,000+
```

---

### Step 2: Update Labels (After Market Close)

After market closes, update actual returns for feature snapshots:

```bash
# Update labels for all symbols on a specific date
.venv/bin/python manage.py update_daytrading_labels \
    --date 2024-10-10

# Or update labels for a specific symbol
.venv/bin/python manage.py update_daytrading_labels \
    --date 2024-10-10 \
    --symbol AAPL \
    --exchange NASDAQ
```

**What this does:**
- Populates label fields (`intraday_return`, `max_favorable_excursion`, `max_adverse_excursion`) for feature snapshots
- Uses finalized `DaySymbol` data to compute actual returns
- Sets `label_ready=True` on updated snapshots

**Note:** This step is automatically run by Celery Beat at 9:30 PM on weekdays via the `complete_daily_feature_labels` task.

---

### Step 3: Train the New Model

Train the improved model on your feature snapshots:

```bash
.venv/bin/python manage.py train_daytrading_model \
    --start-date 2024-04-01 \
    --end-date 2024-10-01 \
    --min-rows 500
```

**What this does:**
- Loads FeatureSnapshot data from database
- Trains HistGradientBoostingRegressor with improved hyperparameters
- Performs 5-fold TimeSeriesSplit cross-validation (NO DATA LEAKAGE)
- Saves model + imputer to `artifacts/daytrading/intraday_model.joblib`
- Saves metadata to `artifacts/daytrading/intraday_model_meta.json`

**Expected output:**
```
Loading dataset...
Loaded 20,000 samples with 35 features

Training model with TimeSeriesSplit (5 folds)...
Fold 1/5: R² = 0.12, MAE = 0.0087
Fold 2/5: R² = 0.15, MAE = 0.0082
Fold 3/5: R² = 0.11, MAE = 0.0091
Fold 4/5: R² = 0.14, MAE = 0.0085
Fold 5/5: R² = 0.13, MAE = 0.0088

Mean R²: 0.13 (±0.014)
Mean MAE: 0.0087 (±0.0003)

Training final model on full dataset...
Model trained and saved to artifacts/daytrading/intraday_model.joblib
```

**Interpreting Metrics:**
- **R² = 0.10-0.15**: Good for intraday prediction (most returns are noise)
- **MAE ≈ 0.8-1%**: Average prediction error of 0.8-1% return
- **R² < 0**: BAD - Model is worse than predicting mean, don't use!
- **MAE > 2%**: BAD - Predictions are too inaccurate

---

### Step 4: Backtest the Model

Test the model on out-of-sample data (data NOT used in training):

```bash
.venv/bin/python manage.py backtest_daytrading \
    --start-date 2024-10-02 \
    --end-date 2024-10-11 \
    --bankroll 10000 \
    --max-positions 5
```

**What this does:**
- Loads test period feature snapshots
- Generates predictions using trained model
- Simulates trading with realistic costs:
  - Commission: $0.0035/share
  - Slippage: 0.05% (5 bps)
- Tracks equity curve, trades, and performance metrics

**Expected output:**
```
Backtest Summary
  starting_capital: 10000.0
  ending_capital: 10150.25
  total_return: 0.015025 (1.50%)
  annualized_return: 0.1841 (18.41%)
  max_drawdown: 0.0324 (3.24%)
  win_rate: 0.52 (52%)
  trades: 50
  sharpe: 1.23
Trades executed: 50
```

**Interpreting Backtest Results:**

| Metric | Good | Acceptable | Bad |
|--------|------|------------|-----|
| Annualized Return | >20% | 10-20% | <10% |
| Sharpe Ratio | >1.5 | 1.0-1.5 | <1.0 |
| Win Rate | >53% | 48-53% | <48% |
| Max Drawdown | <15% | 15-25% | >25% |

**⚠️ WARNING SIGNS:**
- Win rate <48%: Model isn't better than random
- Sharpe <0.5: Risk-adjusted returns are poor
- Max drawdown >30%: Too risky for live trading

---

### Step 5: Analyze Results

Check the saved model metadata:

```bash
cat artifacts/daytrading/intraday_model_meta.json
```

**Example output:**
```json
{
  "metrics": {
    "r2_mean": 0.13,
    "r2_std": 0.014,
    "mae_mean": 0.0087,
    "mae_std": 0.0003,
    "n_samples": 20000,
    "n_features": 35,
    "trained_at": "2024-10-11T14:30:00+00:00",
    "model_type": "HistGradientBoostingRegressor"
  },
  "feature_columns": [
    "return_1d",
    "return_3d",
    "return_5d",
    ...
  ],
  "target": "intraday_return",
  "model_class": "HistGradientBoostingRegressor"
}
```

---

## 📊 STEP-BY-STEP: Test Live Trading (Paper Trading)

### Step 1: Generate Today's Recommendations

```bash
.venv/bin/python manage.py shell
```

```python
from datetime import date
from zimuabull.daytrading.trading_engine import generate_recommendations

# Generate recommendations for today
recommendations = generate_recommendations(
    trade_date=date.today(),
    max_positions=5,
    bankroll=10000,
    exchange_filter="NASDAQ"  # or "TSE", "NYSE", or None for all
)

# Review recommendations
for idx, rec in enumerate(recommendations, 1):
    print(f"\n{idx}. {rec.symbol.symbol} ({rec.symbol.exchange.code})")
    print(f"   Entry: ${rec.entry_price:.2f}")
    print(f"   Target: ${rec.target_price:.2f} (R:R = {(rec.target_price/rec.entry_price - 1) / (1 - rec.stop_price/rec.entry_price):.2f})")
    print(f"   Stop: ${rec.stop_price:.2f}")
    print(f"   Shares: {rec.shares}")
    print(f"   Confidence: {rec.confidence_score:.1f}/100")
    print(f"   Predicted Return: {rec.predicted_return:.2%}")
```

**Expected output:**
```
1. AAPL (NASDAQ)
   Entry: $178.50
   Target: $181.20 (R:R = 1.52)
   Stop: $176.75
   Shares: 28.0
   Confidence: 67.3/100
   Predicted Return: 1.25%

2. MSFT (NASDAQ)
   Entry: $335.80
   Target: $340.50 (R:R = 1.50)
   Stop: $332.75
   Shares: 14.0
   Confidence: 63.8/100
   Predicted Return: 1.10%
...
```

---

### Step 2: Execute Recommendations (Manual)

For paper trading, manually track these trades:

```python
# In shell
from zimuabull.models import Portfolio
from zimuabull.daytrading.trading_engine import execute_recommendations

# Get your paper trading portfolio
portfolio = Portfolio.objects.get(user_id=1, name="Paper Trading")

# Execute the recommendations (creates PortfolioTransaction records)
positions = execute_recommendations(
    recommendations=recommendations,
    portfolio=portfolio,
    trade_date=date.today()
)

print(f"\nExecuted {len(positions)} positions:")
for pos in positions:
    print(f"  {pos.symbol.symbol}: {pos.shares} shares @ ${pos.entry_price}")
```

---

### Step 3: Monitor Positions During Day

Set up monitoring (run every 10 minutes during market hours):

```python
# In a scheduled task or cron job
from zimuabull.daytrading.trading_engine import monitor_positions

# This will auto-close positions that hit stop/target
monitor_positions(portfolio)
```

**Or manually check:**
```python
from zimuabull.daytrading.trading_engine import get_open_day_trade_positions, fetch_live_price

positions = get_open_day_trade_positions(portfolio, trade_date=date.today())

for pos in positions:
    current_price = fetch_live_price(pos.symbol)
    pnl = (current_price - float(pos.entry_price)) * float(pos.shares)
    pnl_pct = (current_price / float(pos.entry_price) - 1) * 100

    print(f"{pos.symbol.symbol}: ${current_price:.2f} | P&L: ${pnl:.2f} ({pnl_pct:+.2f}%)")

    if current_price >= float(pos.target_price):
        print(f"  ✅ TARGET HIT!")
    elif current_price <= float(pos.stop_price):
        print(f"  ❌ STOP HIT!")
```

---

### Step 4: Close All Positions at End of Day

```python
from zimuabull.daytrading.trading_engine import close_all_positions

# Close all remaining positions at market close (4:00 PM ET)
close_all_positions(portfolio)

print("All positions closed. Daily snapshot created.")
```

---

### Step 5: Review Daily Performance

```python
from zimuabull.models import PortfolioSnapshot, DayTradePosition

# Get today's snapshot
snapshot = PortfolioSnapshot.objects.filter(
    portfolio=portfolio,
    date=date.today()
).first()

if snapshot:
    print(f"\nDaily Performance:")
    print(f"  Total Value: ${snapshot.total_value}")
    print(f"  Gain/Loss: ${snapshot.gain_loss} ({snapshot.gain_loss_percent:.2f}%)")

# Review closed positions
closed_positions = DayTradePosition.objects.filter(
    portfolio=portfolio,
    trade_date=date.today(),
    status='CLOSED'
)

wins = 0
losses = 0
total_pnl = 0

for pos in closed_positions:
    pnl = (float(pos.exit_price) - float(pos.entry_price)) * float(pos.shares)
    total_pnl += pnl
    if pnl > 0:
        wins += 1
    else:
        losses += 1

    print(f"\n{pos.symbol.symbol}:")
    print(f"  Entry: ${pos.entry_price} → Exit: ${pos.exit_price}")
    print(f"  Reason: {pos.exit_reason}")
    print(f"  P&L: ${pnl:.2f}")

print(f"\nWin Rate: {wins}/{wins+losses} ({wins/(wins+losses)*100:.1f}%)")
print(f"Total P&L: ${total_pnl:.2f}")
```

---

## 🚦 When to Retrain the Model

### Retrain If:
1. **Monthly Schedule**: Retrain at least once per month with new data
2. **Performance Degradation**:
   - Win rate drops below 48% for 2+ weeks
   - Sharpe ratio <0.5 for 2+ weeks
   - 3+ consecutive losing days
3. **Market Regime Change**:
   - VIX jumps >30
   - Major market correction (>10% drop)
4. **New Data Available**: After accumulating 1000+ new feature snapshots

### DON'T Retrain If:
- Model is <1 week old
- Only 1-2 bad days (normal variance)
- <500 new samples since last training

---

## ⚠️ REMAINING TASKS (Not Yet Implemented)

These improvements were identified but not yet coded:

### Medium Priority:
1. **Add More Features** (feature_builder.py):
   - Market correlation features (S&P 500, sector ETFs)
   - Time-based features (day_of_week, month_end, earnings season)
   - Order flow features (bid/ask spread if available)

2. **Kelly Criterion Position Sizing** (trading_engine.py):
   - Track historical win rates per symbol
   - Use Kelly formula for position sizing instead of equal weight

3. **Model Performance Monitoring** (create new model):
   - Add `ModelPredictionLog` table to track predictions vs actuals
   - Alert when MAE increases >50% vs training
   - Track model drift over time

4. **Winsorize Target Variable** (dataset.py):
   - Clip extreme outliers (1st/99th percentile)
   - Reduce impact of flash crashes on training

5. **Walk-Forward Analysis**:
   - Implement rolling retraining (monthly)
   - Test on expanding window vs fixed window

### Low Priority:
6. **Ensemble Models**: Combine HistGradientBoosting + Random Forest
7. **Regime Detection**: Different models for bull/bear markets
8. **Reinforcement Learning**: For execution timing

---

## 📈 Success Metrics

### Track These Weekly:

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Win Rate | >52% | <50% | <48% |
| Avg Win / Avg Loss | >1.5 | <1.3 | <1.0 |
| Sharpe Ratio | >1.2 | <0.8 | <0.5 |
| Max Drawdown | <15% | <20% | >25% |
| Daily P&L Volatility | <2% | <3% | >4% |

### Track These Monthly:

| Metric | Target | Warning |
|--------|--------|---------|
| Model MAE | <1% | >1.5% |
| Prediction Correlation | >0.3 | <0.2 |
| Number of Trades | 50-100/month | <20 or >150 |
| Commission Costs | <1% of returns | >3% |

---

## 🔍 Debugging Tips

### Model Won't Train:
```bash
# Check feature data
.venv/bin/python manage.py shell
```
```python
from zimuabull.models import FeatureSnapshot
from zimuabull.daytrading.constants import FEATURE_VERSION

count = FeatureSnapshot.objects.filter(
    feature_version=FEATURE_VERSION,
    label_ready=True
).count()

print(f"Label-ready snapshots: {count}")
# Need at least 500
```

### Predictions Are All Zero:
```python
# Check model file exists
from pathlib import Path
from zimuabull.daytrading.constants import MODEL_DIR, MODEL_FILENAME

model_path = MODEL_DIR / MODEL_FILENAME
print(f"Model exists: {model_path.exists()}")

# Check model metadata
import json
meta_path = MODEL_DIR / "intraday_model_meta.json"
with open(meta_path) as f:
    print(json.load(f))
```

### Backtest Shows Unrealistic Returns:
- Check transaction costs are applied
- Verify you're using out-of-sample data (dates AFTER training end_date)
- Look for data leakage (features computed with future data)

---

## 📞 Support

If you encounter issues:
1. Check Django logs: `tail -f logs/django.log`
2. Check Celery logs: `tail -f logs/celery.log`
3. Run Django checks: `.venv/bin/python manage.py check`
4. Verify database: `.venv/bin/python manage.py dbshell`

---

**Last Updated:** 2024-10-11
**Model Version:** v1 (HistGradientBoostingRegressor)
**Commission Structure:** Interactive Brokers Tiered Pricing

---

## 🐛 Common Issues

### Issue: KeyError: 'intraday_return' When Training

**Error Message:**
```
KeyError: 'intraday_return'
```

**Cause:** No feature snapshots with labels exist for your training date range, or there's a feature version mismatch.

**Diagnosis:**
```bash
.venv/bin/python << 'PYEOF'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from zimuabull.models import FeatureSnapshot
from zimuabull.daytrading.constants import FEATURE_VERSION
from datetime import datetime

start_date = datetime.strptime("2024-04-01", "%Y-%m-%d").date()
end_date = datetime.strptime("2024-10-01", "%Y-%m-%d").date()

print(f"Current FEATURE_VERSION: {FEATURE_VERSION}\n")

# Check all versions
all_snapshots = FeatureSnapshot.objects.filter(
    trade_date__gte=start_date,
    trade_date__lte=end_date
)

for version in all_snapshots.values_list('feature_version', flat=True).distinct():
    total = all_snapshots.filter(feature_version=version).count()
    labeled = all_snapshots.filter(feature_version=version, label_ready=True).count()
    print(f"Version '{version}':")
    print(f"  Total: {total}")
    print(f"  Labeled: {labeled}\n")

# Check current version
current_labeled = FeatureSnapshot.objects.filter(
    trade_date__gte=start_date,
    trade_date__lte=end_date,
    feature_version=FEATURE_VERSION,
    label_ready=True
).count()

print(f"✓ {FEATURE_VERSION} snapshots with labels: {current_labeled}")
print(f"✓ Minimum needed for training: 500")

if current_labeled < 500:
    print(f"\n❌ INSUFFICIENT DATA - Need at least 500 labeled snapshots")
PYEOF
```

**Solution:**

If no current version snapshots exist:
```bash
# 1. Generate features for your date range
.venv/bin/python manage.py generate_daytrading_features \
    --start-date 2024-04-01 \
    --end-date 2024-10-01 \
    --overwrite

# 2. Update labels for each trading day
# (Or wait for Celery Beat to run nightly at 9:30 PM)
for date in $(seq -f "2024-04-%02g" 1 30); do
    .venv/bin/python manage.py update_daytrading_labels --date $date
done
```

**Quick Fix for Testing:**
Use a more recent date range that has labeled data:
```bash
.venv/bin/python manage.py train_daytrading_model \
    --start-date 2025-09-01 \
    --end-date 2025-10-01 \
    --min-rows 100
```

---

### Issue: Model Training Completes But R² is Negative

**Cause:** Not enough training data, or features aren't predictive.

**Solution:**
1. Check you have at least 500 labeled snapshots
2. Ensure date range covers multiple months
3. Verify market data quality (no missing OHLCV data)

---

### Issue: Backtest Shows 0% Returns

**Cause:** Model file doesn't exist or predictions are all the same.

**Check:**
```bash
ls -lh artifacts/daytrading/intraday_model.joblib
cat artifacts/daytrading/intraday_model_meta.json
```

**Solution:** Retrain the model following Step 3.

