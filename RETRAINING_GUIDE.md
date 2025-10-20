# Complete Day Trading Model Retraining Guide

This guide walks through **every step** needed to retrain the ZimuaBull day trading algorithm from scratch.

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Data Pipeline](#data-pipeline)
4. [Feature Generation](#feature-generation)
5. [Label Generation](#label-generation)
6. [Model Training](#model-training)
7. [Backtesting](#backtesting)
8. [Deployment](#deployment)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The day trading model predicts **intraday returns** (open-to-close price movements) for stocks using technical indicators and historical features.

### Model Pipeline

```
Raw Stock Data (DaySymbol)
    ↓
Technical Indicators (RSI, MACD, OBV)
    ↓
Feature Snapshots (FeatureSnapshot)
    ↓
Label Generation (intraday_return, max_favorable_excursion, etc.)
    ↓
Model Training (VotingRegressor Ensemble)
    ↓
Backtesting
    ↓
Deployment
```

### File Locations

- **Model artifacts**: `artifacts/daytrading/`
  - `intraday_model_v2.joblib` - Trained model + imputer + feature columns
  - `intraday_model_v2_meta.json` - Model metadata (metrics, timestamp, etc.)
- **Feature version**: `v2` (current) - See [zimuabull/daytrading/constants.py:7](zimuabull/daytrading/constants.py#L7)
- **Target variable**: `intraday_return` - Percentage return from open to close

---

## Prerequisites

### 1. Database Requirements

Your database must have:

#### **DaySymbol Records** (Historical OHLCV data)

At least **60-90 days** of historical daily stock data for each symbol you want to trade.

**Required fields**:
- `date`, `open`, `high`, `low`, `close`, `volume`
- `obv`, `obv_signal`, `obv_signal_sum` (On-Balance Volume indicators)
- `price_diff`, `thirty_price_diff`, `thirty_close_trend`
- `rsi`, `macd`, `macd_signal`, `macd_histogram` (Technical indicators)

**Check your data**:
```bash
# Count DaySymbol records
.venv/bin/python manage.py shell -c "
from zimuabull.models import DaySymbol
print(f'Total DaySymbol records: {DaySymbol.objects.count():,}')
print(f'Date range: {DaySymbol.objects.earliest(\"date\").date} to {DaySymbol.objects.latest(\"date\").date}')
"
```

#### **Symbol Records**

Active symbols from your target exchange (e.g., NASDAQ).

**Check your symbols**:
```bash
# Count symbols by exchange
.venv/bin/python manage.py shell -c "
from zimuabull.models import Symbol
from django.db.models import Count
symbols = Symbol.objects.values('exchange__code').annotate(count=Count('id'))
for s in symbols:
    print(f'{s[\"exchange__code\"]}: {s[\"count\"]} symbols')
"
```

### 2. Technical Indicators

**CRITICAL**: All DaySymbol records must have RSI and MACD calculated.

**Why?** The feature builder uses `rsi`, `macd`, `macd_signal`, and `macd_histogram` from DaySymbol records. If these are NULL, features will be incomplete and the model will perform poorly.

**Calculate technical indicators**:
```bash
# Calculate for all symbols (first time)
.venv/bin/python manage.py calculate_technical_indicators

# Or for specific exchange
.venv/bin/python manage.py calculate_technical_indicators --exchange NASDAQ

# Or for specific symbol
.venv/bin/python manage.py calculate_technical_indicators --symbol AAPL --exchange NASDAQ
```

**Verify indicators**:
```bash
# Check if RSI/MACD are populated
.venv/bin/python manage.py shell -c "
from zimuabull.models import DaySymbol
total = DaySymbol.objects.count()
with_rsi = DaySymbol.objects.filter(rsi__isnull=False).count()
with_macd = DaySymbol.objects.filter(macd__isnull=False).count()
print(f'DaySymbol records with RSI: {with_rsi:,} / {total:,} ({with_rsi/total*100:.1f}%)')
print(f'DaySymbol records with MACD: {with_macd:,} / {total:,} ({with_macd/total*100:.1f}%)')
"
```

**Expected output**: Should be >95% populated for symbols with enough history.

### 3. Market Indices & Regimes

The enriched feature set and regime adapter require:

- Market index price history (including `^VIX`) in `MarketIndexData`
- Recent `MarketRegime` records for each tracked index

**Populate/refresh index data**:
```bash
.venv/bin/python manage.py populate_market_indices --create-indices
.venv/bin/python manage.py populate_market_indices --fetch-data --days 365
```

**Backfill regimes**:
```bash
.venv/bin/python manage.py calculate_market_regimes --days 365
```

The retrain command now verifies this and will abort if recent index data is missing, warning if regimes need to be regenerated.

### 3. Minimum History Requirement

Each symbol needs at least **40 days** of historical data before its first feature snapshot can be generated ([constants.py:8](zimuabull/daytrading/constants.py#L8)).

**Why?** Features include:
- 20-day momentum calculations
- 20-day volume averages
- 14-day ATR (Average True Range)
- 30-day trend analysis

---

## Data Pipeline

### Step 0: Ensure Fresh Data

**If you don't have recent stock data**, you need to run your data collection process first.

```bash
# This depends on your setup - typically a Celery task or management command
# Example (adjust based on your scanners):
.venv/bin/python manage.py shell -c "
from zimuabull.tasks.scan import scan_market
scan_market.delay()  # Or scan_market() if not using Celery
"
```

**Verify you have recent data**:
```bash
.venv/bin/python manage.py shell -c "
from zimuabull.models import DaySymbol
from datetime import date
today = date.today()
recent = DaySymbol.objects.filter(date=today).count()
print(f'DaySymbol records for {today}: {recent:,}')
if recent == 0:
    print('⚠️ WARNING: No data for today! Run data collection first.')
"
```

---

## Feature Generation

Features are pre-computed and stored in `FeatureSnapshot` records. Each snapshot contains:
- **Features**: Technical indicators, momentum, volume ratios, etc. (JSON field)
- **Labels**: Actual outcomes (intraday_return, max_favorable_excursion, etc.)
- **Metadata**: Symbol, date, feature version

### Generate Features for a Date Range

**For training, you typically want 60-90 days of features.**

#### Option 1: Backfill Historical Features

```bash
# Generate features for the last 90 days
.venv/bin/python manage.py generate_daytrading_features \
  --start-date 2025-07-20 \
  --end-date 2025-10-18 \
  --exchange NASDAQ
```

**Parameters**:
- `--start-date`: First trading date to process (YYYY-MM-DD)
- `--end-date`: Last trading date to process (YYYY-MM-DD) - defaults to today
- `--exchange`: Filter by exchange (NASDAQ, NYSE, TSE, etc.)
- `--symbol`: Process only specific symbol (optional)
- `--overwrite`: Regenerate features even if they already exist

**Time Estimate**:
- ~1-5 seconds per symbol per day
- For 1000 symbols × 90 days = ~90,000 snapshots = **2-8 hours**

**Progress tracking**:
The command shows real-time progress:
```
Processing 1000 symbols...
Total trading days to process: 63
[1/63] 2025-07-20 | Day: 856 snapshots | Total: 856 | Progress: 1.6% | Speed: 12.3 days/min | ETA: 5m 2s
[2/63] 2025-07-21 | Day: 859 snapshots | Total: 1715 | Progress: 3.2% | Speed: 13.1 days/min | ETA: 4m 40s
...
```

#### Option 2: Generate Features for Today Only

```bash
# Generate features for today's trading
.venv/bin/python manage.py generate_daytrading_features \
  --date 2025-10-18 \
  --exchange NASDAQ
```

**Use this when**:
- You just want to add today's features to an existing dataset
- You're running daily automated updates

### Verify Features Were Generated

```bash
# Check FeatureSnapshot count
.venv/bin/python manage.py shell -c "
from zimuabull.models import FeatureSnapshot
from zimuabull.daytrading.constants import FEATURE_VERSION

total = FeatureSnapshot.objects.filter(feature_version=FEATURE_VERSION).count()
with_labels = FeatureSnapshot.objects.filter(feature_version=FEATURE_VERSION, label_ready=True).count()

print(f'Feature version: {FEATURE_VERSION}')
print(f'Total snapshots: {total:,}')
print(f'Snapshots with labels: {with_labels:,} ({with_labels/total*100:.1f}% if total else 0)')
print(f'Snapshots without labels: {total - with_labels:,}')
"
```

**Expected output**:
```
Feature version: v2
Total snapshots: 85,432
Snapshots with labels: 84,128 (98.5%)
Snapshots without labels: 1,304
```

**Why some snapshots don't have labels?**
- Labels require the **actual trading day** to have completed
- Today's features won't have labels until tomorrow's data is available
- Missing DaySymbol records for certain dates

---

## Label Generation

Labels are the **actual outcomes** we're trying to predict:
- `intraday_return`: Percentage return from open to close price
- `max_favorable_excursion`: Maximum profit during the day
- `max_adverse_excursion`: Maximum loss during the day

### Generate Labels for Previous Days

**IMPORTANT**: You can only generate labels for days where the trading has **already completed** and DaySymbol data exists.

```bash
# Update labels for a specific date (one day ago)
.venv/bin/python manage.py update_daytrading_labels --date 2025-10-17

# Or for a specific symbol
.venv/bin/python manage.py update_daytrading_labels \
  --date 2025-10-17 \
  --symbol AAPL \
  --exchange NASDAQ
```

### Batch Update Labels

If you generated features for a date range but forgot to update labels:

```bash
# Manually loop through dates (replace with your range)
for date in {20..17}; do
  .venv/bin/python manage.py update_daytrading_labels --date 2025-10-$date
done
```

Or use Python:
```bash
.venv/bin/python manage.py shell -c "
from datetime import date, timedelta
from zimuabull.daytrading.feature_builder import update_labels_for_date

end_date = date(2025, 10, 17)  # Yesterday
start_date = end_date - timedelta(days=90)

current = start_date
while current <= end_date:
    if current.weekday() < 5:  # Skip weekends
        updated = update_labels_for_date(current)
        print(f'{current}: Updated {updated} labels')
    current += timedelta(days=1)
"
```

### Verify Labels

```bash
# Check label coverage
.venv/bin/python manage.py shell -c "
from zimuabull.models import FeatureSnapshot
from zimuabull.daytrading.constants import FEATURE_VERSION
from datetime import date, timedelta

# Get snapshots from last 30 days
cutoff = date.today() - timedelta(days=30)
recent = FeatureSnapshot.objects.filter(
    feature_version=FEATURE_VERSION,
    trade_date__gte=cutoff
)

total = recent.count()
labeled = recent.filter(label_ready=True).count()

print(f'Recent snapshots (last 30 days): {total:,}')
print(f'With labels: {labeled:,} ({labeled/total*100:.1f}%)')
print(f'Without labels: {total-labeled:,}')
"
```

---

## Model Training

Now that you have features and labels, you can train the model!

### Training Command

```bash
# Train with all available data
.venv/bin/python manage.py retrain_daytrading_model

# Or specify date range
.venv/bin/python manage.py retrain_daytrading_model \
  --start-date 2025-07-20 \
  --end-date 2025-10-17 \
  --min-rows 1000
```

**Parameters**:
- `--start-date`: Earliest feature snapshot date to include
- `--end-date`: Latest feature snapshot date to include
- `--min-rows`: Minimum samples required to train (default: 500)

### Training Process

The command will:

1. **Load Dataset** (~10-30 seconds)
   - Loads all FeatureSnapshot records with `label_ready=True`
   - Encodes categorical features (exchange_code)
   - Handles missing values with median imputation

2. **Train Model** (~3-12 minutes depending on dataset size)
   - Tunes three base learners (HistGradientBoosting, RandomForest, GradientBoosting) via RandomizedSearchCV
   - Builds a `VotingRegressor` ensemble with the tuned estimators
   - Uses TimeSeriesSplit cross-validation (prevents look-ahead bias)
   - Logs best parameters for each base model

3. **Save Model**
   - Saves to `artifacts/daytrading/intraday_model_v2.joblib`
   - Includes model, imputer, and feature columns
   - Saves metadata to `intraday_model_v2_meta.json`

### Understanding Training Output

```
📊 Loading dataset...
✓ Loaded 84,128 samples with 42 features

🔧 Training Ensemble VotingRegressor...
   • RandomizedSearchCV hyperparameter tuning (n_iter=25)
   • Training may take 3-12 minutes depending on dataset size...

✓ Model training complete!

📈 Cross-Validation Metrics:
   • R² Score:  0.0847 (±0.0123)
   • MAE Score: 0.0134 (±0.0008)
   • Samples:   84,128
   • Features:  42

💡 Interpretation:
   ✓ Good R² for intraday prediction
   ✓ Good MAE (<1.5% average error)

💾 Saving model...

✓ Model saved to: artifacts/daytrading/intraday_model_v2.joblib
✓ Model type: EnsembleVotingRegressor
   • hgb: {'learning_rate': 0.05, 'l2_regularization': 0.5, ...}
   • rf: {'max_depth': 8, 'min_samples_split': 5, ...}
   • gbr: {'max_depth': 3, 'n_estimators': 400, ...}
✓ Trained at: 2025-10-18T14:32:11.547291+00:00

🎯 Next Steps:
   1. Run backtest: python manage.py backtest_daytrading --start-date <date> --end-date <date>
   2. Review backtest metrics (Sharpe > 1.0, Win Rate > 48%)
   3. Paper trade for 2-4 weeks before going live
```

### Interpreting Metrics

#### R² Score (Coefficient of Determination)

**What it measures**: How well the model explains variance in intraday returns.

- **>0.15**: 🎉 Excellent for intraday prediction (extremely rare)
- **0.08-0.15**: ✅ Good - model has predictive power
- **0.03-0.08**: ⚠️ Marginal - model barely beats baseline
- **<0.03**: ❌ Poor - model is not learning meaningful patterns

**Why low R² is OK for intraday trading?**
- Stock price movements are inherently noisy
- Even small edge (R² > 0.05) can be profitable with proper risk management
- Focus on **directional accuracy** (win rate) rather than exact predictions

#### MAE (Mean Absolute Error)

**What it measures**: Average prediction error as a percentage.

- **<0.01 (1%)**: 🎉 Excellent precision
- **0.01-0.015 (1-1.5%)**: ✅ Good - acceptable error
- **0.015-0.02 (1.5-2%)**: ⚠️ Marginal - predictions are fuzzy
- **>0.02 (2%)**: ❌ Poor - too much error for day trading

**Example**: MAE of 0.0134 means predictions are off by ±1.34% on average.

### Training Best Practices

1. **Use at least 60-90 days of data**
   - More data = better generalization
   - But too much old data may include outdated market regimes

2. **Retrain weekly**
   - Markets evolve, models degrade over time
   - Fresh data keeps predictions relevant

3. **Check for data leakage**
   - The model uses `TimeSeriesSplit` to prevent leakage
   - Never use future data to predict the past

4. **Monitor feature importance**
   - After training, check which features matter most
   - Remove low-importance features to reduce overfitting

---

## Backtesting

**CRITICAL**: Always backtest before deploying!

### Run Backtest

```bash
# Backtest on recent 30 days
.venv/bin/python manage.py backtest_daytrading \
  --start-date 2025-09-18 \
  --end-date 2025-10-17 \
  --bankroll 10000 \
  --max-positions 5
```

**Parameters**:
- `--start-date`: First trading date to simulate
- `--end-date`: Last trading date to simulate
- `--bankroll`: Starting capital (default: $10,000)
- `--max-positions`: Max positions per day (default: 5)

### Backtest Process

The backtest simulates trading with the trained model:

1. **For each trading day**:
   - Load feature snapshots for all symbols
   - Use model to predict intraday returns
   - Select top N symbols with highest predicted returns
   - Allocate capital equally across positions
   - Apply transaction costs (0.05% + commission + slippage)

2. **Calculate outcomes**:
   - Use actual `intraday_return` labels
   - Track equity curve, wins/losses, drawdowns
   - Compute performance metrics

### Understanding Backtest Output

```
📊 Loading backtest dataset...
✓ Loaded 8,432 samples for backtesting

🤖 Loading trained model...
✓ Model loaded successfully

🔄 Running backtest simulation...
   • Starting capital: $10,000.00
   • Max positions: 5
   • Transaction cost: 0.05% + commission
   • Processing...

✓ Backtest complete!

============================================================
📈 BACKTEST RESULTS
============================================================

💰 Capital:
   Starting:   $10,000.00
   Ending:     $11,234.56
   Profit:      $1,234.56

📊 Returns:
   Total Return:           12.35%
   Annualized Return:      52.41%

⚠️  Risk:
   Max Drawdown:           8.23%
   Sharpe Ratio:           1.84

🎯 Trading:
   Win Rate:               54.20%
   Total Trades:              142

============================================================
💡 INTERPRETATION
============================================================

🎉 EXCELLENT PERFORMANCE!
   ✓ All metrics exceed targets
   ✓ Model is ready for paper trading

📋 Target Metrics:
   Annualized Return: >15% (yours: 52.41%)
   Sharpe Ratio:      >1.2  (yours: 1.84)
   Win Rate:          >50%  (yours: 54.2%)
   Max Drawdown:      <20%  (yours: 8.2%)

============================================================

🎯 Next Steps:
   1. ✓ Backtest looks good!
   2. Start paper trading for 2-4 weeks
   3. Monitor daily: Win rate, Sharpe, Drawdown
   4. Go live only if paper trading confirms backtest
```

### Interpreting Backtest Metrics

#### Annualized Return

**What it measures**: Expected yearly return if you traded every day.

- **>20%**: 🎉 Excellent - beats most hedge funds
- **15-20%**: ✅ Good - beats S&P 500 average
- **10-15%**: ⚠️ Marginal - barely beats index funds
- **<10%**: ❌ Poor - not worth the effort/risk

#### Sharpe Ratio

**What it measures**: Risk-adjusted return (return per unit of volatility).

- **>1.5**: 🎉 Excellent - very efficient use of risk
- **1.0-1.5**: ✅ Good - acceptable risk/reward
- **0.5-1.0**: ⚠️ Marginal - too much risk for return
- **<0.5**: ❌ Poor - volatility not justified by returns

**Formula**: `(Return - Risk-Free Rate) / StdDev of Returns × √252`

#### Win Rate

**What it measures**: Percentage of profitable trades.

- **>55%**: 🎉 Excellent - high hit rate
- **50-55%**: ✅ Good - slight edge
- **48-50%**: ⚠️ Marginal - needs excellent risk management
- **<48%**: ❌ Poor - losing more often than winning

#### Max Drawdown

**What it measures**: Largest peak-to-trough decline in portfolio value.

- **<10%**: 🎉 Excellent - very stable
- **10-20%**: ✅ Good - manageable risk
- **20-30%**: ⚠️ Marginal - significant stress
- **>30%**: ❌ Poor - unacceptable risk

### Backtest Gotchas

⚠️ **Backtests can be misleading!**

1. **Survivorship Bias**
   - Only includes stocks that still exist
   - Excludes delisted/bankrupt companies
   - **Solution**: Accept it, or track delisted symbols

2. **Overfitting**
   - Model memorizes training data
   - Backtest looks great, live trading fails
   - **Solution**: Out-of-sample testing, walk-forward analysis

3. **Transaction Costs**
   - Slippage, commissions, bid-ask spread
   - Can eat 0.1-0.5% per trade
   - **Solution**: Be conservative with cost estimates

4. **Market Regime Changes**
   - Backtest period may not represent future conditions
   - Bull market backtest ≠ bear market performance
   - **Solution**: Test across different market conditions

---

## Deployment

Once you're satisfied with backtest results, you can deploy the model.

### Option 1: Paper Trading (Recommended)

Test the model with **simulated money** before risking real capital.

1. **Set portfolio to paper trading mode**:
   ```bash
   .venv/bin/python manage.py shell -c "
   from zimuabull.models import Portfolio
   portfolio = Portfolio.objects.get(name='Your Portfolio Name')
   portfolio.use_interactive_brokers = False  # Disable live trading
   portfolio.save()
   print(f'Portfolio {portfolio.name} set to paper trading mode')
   "
   ```

2. **Run daily recommendations**:
   The system will generate recommendations but NOT execute real orders.

3. **Monitor for 2-4 weeks**:
   - Track win rate, Sharpe ratio, drawdown
   - Compare to backtest results
   - Look for signs of degradation

### Option 2: Live Trading

**ONLY after successful paper trading!**

1. **Enable Interactive Brokers integration**:
   ```bash
   .venv/bin/python manage.py shell -c "
   from zimuabull.models import Portfolio
   portfolio = Portfolio.objects.get(name='Your Portfolio Name')
   portfolio.use_interactive_brokers = True
   portfolio.ib_host = '127.0.0.1'
   portfolio.ib_port = 7497  # TWS paper: 7497, live: 7496
   portfolio.ib_client_id = 1
   portfolio.save()
   print(f'Portfolio {portfolio.name} enabled for IB trading')
   "
   ```

2. **Start with small capital**:
   - Begin with 10-20% of your intended capital
   - Increase gradually as confidence grows

3. **Monitor actively**:
   - Check positions daily
   - Watch for unexpected behavior
   - Be ready to pause trading if needed

### Automated Retraining Schedule

Set up weekly retraining to keep the model fresh:

```bash
# Add to crontab (runs every Sunday at 2 AM)
0 2 * * 0 cd /path/to/ZimuaBull && .venv/bin/python manage.py retrain_daytrading_model --start-date $(date -d '90 days ago' +\%Y-\%m-\%d) --end-date $(date -d 'yesterday' +\%Y-\%m-\%d) >> /var/log/zimuabull/training.log 2>&1
```

Or use Celery Beat (see [core/settings.py](core/settings.py) CELERY_BEAT_SCHEDULE).

---

## Troubleshooting

### Issue: "No symbols found"

**Problem**: `generate_daytrading_features` says "No symbols found for the provided filters."

**Solution**:
```bash
# Check if symbols exist
.venv/bin/python manage.py shell -c "
from zimuabull.models import Symbol
print(f'Total symbols: {Symbol.objects.count()}')
print('Symbols by exchange:')
for ex in Symbol.objects.values('exchange__code').distinct():
    count = Symbol.objects.filter(exchange__code=ex['exchange__code']).count()
    print(f'  {ex[\"exchange__code\"]}: {count}')
"

# If no symbols, you need to populate them first
# This is specific to your data collection setup
```

### Issue: "Insufficient samples... Need at least 500"

**Problem**: Not enough labeled feature snapshots for training.

**Solution**:
1. Generate more features: `--start-date` further back in time
2. Ensure labels are updated: Run `update_daytrading_labels`
3. Check for data gaps:
   ```bash
   .venv/bin/python manage.py shell -c "
   from zimuabull.models import FeatureSnapshot
   from zimuabull.daytrading.constants import FEATURE_VERSION
   labeled = FeatureSnapshot.objects.filter(feature_version=FEATURE_VERSION, label_ready=True).count()
   print(f'Labeled snapshots: {labeled:,}')
   if labeled < 500:
       print('⚠️ Need more labeled data!')
       print('Run: generate_daytrading_features --start-date <earlier-date>')
       print('Then: update_daytrading_labels for each completed trading day')
   "
   ```

### Issue: "Model file not found"

**Problem**: Trying to backtest or trade without training first.

**Solution**:
```bash
# Check if model exists
ls -lh artifacts/daytrading/

# If not, train it
.venv/bin/python manage.py retrain_daytrading_model
```

### Issue: Backtest shows poor performance (R² < 0, negative returns)

**Possible causes**:
1. **Insufficient training data**: Need at least 60 days
2. **Missing technical indicators**: Run `calculate_technical_indicators`
3. **Data quality issues**: Check for missing DaySymbol records
4. **Feature version mismatch**: Old features with new model
5. **Market regime shift**: Model trained on bull market, tested on bear

**Solutions**:
```bash
# Check data quality
.venv/bin/python manage.py shell -c "
from zimuabull.models import DaySymbol
from datetime import date, timedelta

# Check recent data completeness
cutoff = date.today() - timedelta(days=90)
recent = DaySymbol.objects.filter(date__gte=cutoff)

total = recent.count()
with_rsi = recent.filter(rsi__isnull=False).count()
with_macd = recent.filter(macd__isnull=False).count()

print(f'Recent DaySymbol records (last 90 days): {total:,}')
print(f'With RSI: {with_rsi:,} ({with_rsi/total*100:.1f}%)')
print(f'With MACD: {with_macd:,} ({with_macd/total*100:.1f}%)')

if with_rsi / total < 0.90:
    print('⚠️ WARNING: Missing RSI data! Run calculate_technical_indicators')
if with_macd / total < 0.90:
    print('⚠️ WARNING: Missing MACD data! Run calculate_technical_indicators')
"

# Regenerate features if needed
.venv/bin/python manage.py generate_daytrading_features \
  --start-date 2025-07-20 \
  --end-date 2025-10-17 \
  --overwrite \
  --exchange NASDAQ

# Retrain
.venv/bin/python manage.py retrain_daytrading_model
```

### Issue: Feature generation is too slow

**Problem**: Processing 1000 symbols × 90 days takes many hours.

**Solutions**:

1. **Process in chunks** (by exchange or symbol groups):
   ```bash
   # Process NASDAQ separately
   .venv/bin/python manage.py generate_daytrading_features \
     --start-date 2025-07-20 \
     --end-date 2025-10-17 \
     --exchange NASDAQ
   ```

2. **Parallelize** (modify [feature_builder.py:218-231](zimuabull/daytrading/feature_builder.py#L218-L231)):
   ```python
   # See IMPROVEMENTS.md for parallelization code
   ```

3. **Skip older dates** if you already have features:
   ```bash
   # Only generate last 30 days
   .venv/bin/python manage.py generate_daytrading_features \
     --start-date 2025-09-18 \
     --end-date 2025-10-18 \
     --exchange NASDAQ
   ```

### Issue: Model predicts same value for everything

**Problem**: All predictions are very similar (e.g., always 0.001).

**Possible causes**:
1. **Not enough variance in training data**: All stocks moving similarly
2. **Too much regularization**: Model is overly conservative
3. **Feature scaling issues**: Some features dominating others
4. **Insufficient training**: Model didn't converge

**Solutions**:
1. **Check target distribution**:
   ```bash
   .venv/bin/python manage.py shell -c "
   from zimuabull.daytrading.dataset import load_dataset
   dataset = load_dataset()
   print(f'Mean return: {dataset.targets.mean():.4f}')
   print(f'Std return: {dataset.targets.std():.4f}')
   print(f'Min return: {dataset.targets.min():.4f}')
   print(f'Max return: {dataset.targets.max():.4f}')
   print(f'Target distribution:')
   print(dataset.targets.describe())
   "
   ```

2. **Increase training data**: More diverse market conditions

3. **Adjust hyperparameters** in [modeling.py:46-57](zimuabull/daytrading/modeling.py#L46-L57):
   - Decrease `l2_regularization` (less conservative)
   - Increase `max_depth` (more complex patterns)
   - Increase `max_iter` (more training)

---

## Quick Reference: Complete Retraining Workflow

### From Scratch (First Time)

```bash
# 1. Ensure you have data
.venv/bin/python manage.py shell -c "
from zimuabull.models import DaySymbol
print(f'DaySymbol records: {DaySymbol.objects.count():,}')
"

# 2. Calculate technical indicators (REQUIRED)
.venv/bin/python manage.py calculate_technical_indicators

# 3. Generate features (90 days)
.venv/bin/python manage.py generate_daytrading_features \
  --start-date 2025-07-20 \
  --end-date 2025-10-17 \
  --exchange NASDAQ

# 4. Update labels for completed trading days
# (Loop through each date from start to yesterday)
for date in {20..17}; do
  .venv/bin/python manage.py update_daytrading_labels --date 2025-10-$date
done

# 5. Train model
.venv/bin/python manage.py retrain_daytrading_model

# 6. Backtest
.venv/bin/python manage.py backtest_daytrading \
  --start-date 2025-09-18 \
  --end-date 2025-10-17 \
  --bankroll 10000 \
  --max-positions 5

# 7. Review results and deploy if good
```

### Weekly Retraining (Ongoing)

```bash
# 1. Generate features for new trading days
.venv/bin/python manage.py generate_daytrading_features \
  --start-date 2025-10-14 \
  --end-date 2025-10-18 \
  --exchange NASDAQ

# 2. Update labels for last week (Mon-Fri)
for day in 14 15 16 17 18; do
  .venv/bin/python manage.py update_daytrading_labels --date 2025-10-$day
done

# 3. Retrain (last 90 days)
.venv/bin/python manage.py retrain_daytrading_model \
  --start-date 2025-07-20 \
  --end-date 2025-10-18

# 4. Quick backtest (last 2 weeks)
.venv/bin/python manage.py backtest_daytrading \
  --start-date 2025-10-04 \
  --end-date 2025-10-18

# 5. Deploy updated model (happens automatically when saved)
```

### Daily Feature Generation (For Live Trading)

```bash
# Add today's features (run after market close)
.venv/bin/python manage.py generate_daytrading_features \
  --date $(date +%Y-%m-%d) \
  --exchange NASDAQ

# Update yesterday's labels
.venv/bin/python manage.py update_daytrading_labels \
  --date $(date -d 'yesterday' +%Y-%m-%d)
```

---

## Configuration Files

Key configuration parameters you might want to adjust:

### [zimuabull/daytrading/constants.py](zimuabull/daytrading/constants.py)

```python
FEATURE_VERSION = "v2"          # Change if you modify feature engineering
MIN_HISTORY_DAYS = 40           # Minimum days needed for features
MIN_TRAINING_ROWS = 500         # Minimum samples for training

# Model storage
MODEL_DIR = Path("artifacts") / "daytrading"
MODEL_FILENAME = "intraday_model_v2.joblib"
```

### [zimuabull/daytrading/modeling_ensemble.py](zimuabull/daytrading/modeling_ensemble.py#L20-L120)

```python
base_models = {
    "hgb": (
        HistGradientBoostingRegressor(random_state=random_state),
        {"max_depth": [5, 7, 9], "learning_rate": [0.03, 0.05, 0.08], ...},
    ),
    "rf": (
        RandomForestRegressor(random_state=random_state, n_jobs=-1),
        {"n_estimators": [200, 400, 600], "max_depth": [6, 8, 10, None], ...},
    ),
    "gbr": (
        GradientBoostingRegressor(random_state=random_state),
        {"n_estimators": [200, 400, 600], "learning_rate": [0.03, 0.05, 0.08], ...},
    ),
}

ensemble = VotingRegressor(estimators=estimators_for_ensemble, n_jobs=-1)
ensemble.fit(X, y)
```

### [zimuabull/daytrading/feature_builder.py](zimuabull/daytrading/feature_builder.py#L9-L16)

```python
# Feature engineering lookback windows
LOOKBACK_WINDOWS = [1, 3, 5, 10, 20]    # Momentum periods
VOLUME_WINDOWS = [5, 10, 20]            # Volume averaging periods
ATR_WINDOW = 14                          # Average True Range period
```

---

## Next Steps

After successful retraining:

1. **Monitor Performance**:
   - Track actual vs predicted returns
   - Monitor win rate, Sharpe, drawdown
   - Look for model degradation

2. **Implement Weekly Review** ([services/portfolio_review.py](zimuabull/services/portfolio_review.py)):
   ```bash
   .venv/bin/python manage.py weekly_portfolio_review
   ```

3. **Consider Enhancements** (see [IMPROVEMENTS.md](IMPROVEMENTS.md)):
   - Add news sentiment features
   - Implement ensemble models
   - Add market regime detection
   - Implement automated hyperparameter tuning

4. **Set Up Automated Retraining**:
   - Add to crontab or Celery Beat
   - Run weekly on Sunday nights
   - Include notification on completion

---

## Getting Help

If you encounter issues not covered in this guide:

1. **Check Logs**:
   ```bash
   # Check Celery logs
   tail -f /var/log/zimuabull/celery.log

   # Check Django logs
   tail -f /var/log/zimuabull/django.log
   ```

2. **Inspect Database**:
   ```bash
   .venv/bin/python manage.py shell
   ```

3. **Review Code**:
   - [zimuabull/daytrading/](zimuabull/daytrading/) - All day trading logic
   - [zimuabull/management/commands/](zimuabull/management/commands/) - CLI commands
   - [zimuabull/models.py](zimuabull/models.py) - Data models

4. **Test Components Individually**:
   ```bash
   # Test feature generation for one symbol
   .venv/bin/python manage.py generate_daytrading_features \
     --date 2025-10-17 \
     --symbol AAPL \
     --exchange NASDAQ

   # Test label update for one symbol
   .venv/bin/python manage.py update_daytrading_labels \
     --date 2025-10-17 \
     --symbol AAPL \
     --exchange NASDAQ
   ```

---

**Good luck with your trading! 🚀**

*Remember: Past performance is not indicative of future results. Always manage risk carefully.*
