# Day Trading Model Retraining - Quick Reference

## Complete Workflow (From Scratch)

```bash
# 1️⃣ Calculate Technical Indicators (REQUIRED - Do this first!)
.venv/bin/python manage.py calculate_technical_indicators

# 2️⃣ Generate Features (90 days recommended)
.venv/bin/python manage.py generate_daytrading_features \
  --start-date 2025-07-20 \
  --end-date 2025-10-17 \
  --exchange NASDAQ

# 3️⃣ Update Labels (for each completed trading day)
.venv/bin/python manage.py update_daytrading_labels --date 2025-10-17

# 4️⃣ Retrain (ensemble model with auto HPO)
.venv/bin/python manage.py retrain_daytrading_model

# 5️⃣ Backtest
.venv/bin/python manage.py backtest_daytrading \
  --start-date 2025-09-18 \
  --end-date 2025-10-17 \
  --bankroll 10000 \
  --max-positions 5
```

---

## Weekly Retraining

```bash
# Monday morning routine (after market close Friday)

# 1. Add last week's features
.venv/bin/python manage.py generate_daytrading_features \
  --start-date 2025-10-14 \
  --end-date 2025-10-18 \
  --exchange NASDAQ

# 2. Update last week's labels
for day in 14 15 16 17 18; do
  .venv/bin/python manage.py update_daytrading_labels --date 2025-10-$day
done

# 3. Retrain (ensemble, last 90 days)
.venv/bin/python manage.py retrain_daytrading_model \
  --start-date 2025-07-20 \
  --end-date 2025-10-18

# 4. Quick backtest
.venv/bin/python manage.py backtest_daytrading \
  --start-date 2025-10-04 \
  --end-date 2025-10-18
```

---

## Daily Feature Update (For Live Trading)

```bash
# Run after market close each day

# Today's features
.venv/bin/python manage.py generate_daytrading_features \
  --date $(date +%Y-%m-%d) \
  --exchange NASDAQ

# Yesterday's labels
.venv/bin/python manage.py update_daytrading_labels \
  --date $(date -d 'yesterday' +%Y-%m-%d)
```

---

## Verification Commands

### Check Data Availability
```bash
.venv/bin/python manage.py shell -c "
from zimuabull.models import DaySymbol, FeatureSnapshot
from zimuabull.daytrading.constants import FEATURE_VERSION

# DaySymbol data
total_days = DaySymbol.objects.count()
with_rsi = DaySymbol.objects.filter(rsi__isnull=False).count()
print(f'DaySymbol records: {total_days:,}')
print(f'With RSI: {with_rsi:,} ({with_rsi/total_days*100:.1f}%)')

# Feature snapshots
snapshots = FeatureSnapshot.objects.filter(feature_version=FEATURE_VERSION)
labeled = snapshots.filter(label_ready=True)
print(f'\\nFeature snapshots (v{FEATURE_VERSION}): {snapshots.count():,}')
print(f'With labels: {labeled.count():,} ({labeled.count()/snapshots.count()*100:.1f}%)')
"
```

### Check Model Exists
```bash
ls -lh artifacts/daytrading/
```

### Check Recent Data
```bash
.venv/bin/python manage.py shell -c "
from zimuabull.models import DaySymbol
from datetime import date
today = date.today()
recent = DaySymbol.objects.filter(date=today).count()
print(f'DaySymbol records for {today}: {recent:,}')
"
```

---

## Troubleshooting Quick Fixes

### Missing RSI/MACD
```bash
# Recalculate all technical indicators
.venv/bin/python manage.py calculate_technical_indicators
```

### Need More Training Data
```bash
# Extend date range further back
.venv/bin/python manage.py generate_daytrading_features \
  --start-date 2025-05-01 \
  --end-date 2025-10-17 \
  --exchange NASDAQ
```

### Features Without Labels
```bash
# Batch update labels for date range
for month in 07 08 09 10; do
  for day in {01..31}; do
    .venv/bin/python manage.py update_daytrading_labels --date 2025-$month-$day 2>/dev/null
  done
done
```

### Poor Backtest Performance
```bash
# 1. Verify data quality
.venv/bin/python manage.py calculate_technical_indicators --force

# 2. Regenerate features with fresh data
.venv/bin/python manage.py generate_daytrading_features \
  --start-date 2025-07-20 \
  --end-date 2025-10-17 \
  --overwrite \
  --exchange NASDAQ

# 3. Retrain (ensemble default)
.venv/bin/python manage.py retrain_daytrading_model
```

---

## Target Metrics

### Training Metrics (model quality)
- **R² Score**: >0.08 (Good), >0.15 (Excellent)
- **MAE**: <0.015 (1.5% avg error)

### Backtest Metrics (profitability)
- **Annualized Return**: >15%
- **Sharpe Ratio**: >1.2
- **Win Rate**: >50%
- **Max Drawdown**: <20%

---

## Important Files

### Commands
- `generate_daytrading_features.py` - Create feature snapshots
- `update_daytrading_labels.py` - Add actual outcomes
- `retrain_daytrading_model.py` - Retrain ensemble model with HPO
- `backtest_daytrading.py` - Simulate trading
- `calculate_technical_indicators.py` - RSI/MACD calculation
- `calculate_market_regimes.py` - Backfill market regime classifications

### Code
- `zimuabull/daytrading/feature_builder.py` - Feature engineering
- `zimuabull/daytrading/modeling.py` - Model training
- `zimuabull/daytrading/backtest.py` - Backtesting logic
- `zimuabull/daytrading/constants.py` - Configuration

### Artifacts
- `artifacts/daytrading/intraday_model_v2.joblib` - Trained model
- `artifacts/daytrading/intraday_model_v2_meta.json` - Metadata

---

## Common Patterns

### Regenerate Everything
```bash
# Nuclear option: Start completely fresh
rm -rf artifacts/daytrading/*

# Recalculate indicators
.venv/bin/python manage.py calculate_technical_indicators --force

# Generate 90 days of features
.venv/bin/python manage.py generate_daytrading_features \
  --start-date 2025-07-20 \
  --end-date 2025-10-17 \
  --overwrite \
  --exchange NASDAQ

# Update all labels
for date in {2025-07-20..2025-10-17}; do
  .venv/bin/python manage.py update_daytrading_labels --date $date 2>/dev/null
done

# Retrain (ensemble + HPO)
.venv/bin/python manage.py retrain_daytrading_model
```

### Automation

#### Cron Job (Weekly Retraining)
```bash
# Add to crontab: Sunday 2 AM (includes regime refresh + ensemble retrain)
0 1 * * 0 /path/to/ZimuaBull/.venv/bin/python /path/to/ZimuaBull/manage.py populate_market_indices --fetch-data --days 7
30 1 * * 0 /path/to/ZimuaBull/.venv/bin/python /path/to/ZimuaBull/manage.py calculate_market_regimes --days 7
0 2 * * 0 /path/to/ZimuaBull/.venv/bin/python /path/to/ZimuaBull/manage.py retrain_daytrading_model --start-date $(date -d '90 days ago' +\%Y-\%m-\%d) --end-date $(date -d 'yesterday' +\%Y-\%m-\%d)
```

### Daily Feature Generation
```bash
# Add to crontab: Weekdays after market close (5 PM ET)
0 17 * * 1-5 /path/to/ZimuaBull/.venv/bin/python /path/to/ZimuaBull/manage.py generate_daytrading_features --date $(date +\%Y-\%m-\%d) --exchange NASDAQ
```

---

## Pipeline Sequence

```
1. Raw Data Collection
   └─> DaySymbol records (OHLCV)

2. Technical Indicators
   └─> calculate_technical_indicators
       └─> RSI, MACD, MACD Signal, MACD Histogram

3. Feature Engineering
   └─> generate_daytrading_features
       └─> FeatureSnapshot (features JSON, no labels yet)

4. Label Generation (next day)
   └─> update_daytrading_labels
       └─> FeatureSnapshot (features + labels)

5. Model Training
   └─> retrain_daytrading_model
       └─> Load labeled snapshots
       └─> Train ensemble VotingRegressor (with HPO)
       └─> Save to artifacts/daytrading/

6. Backtesting
   └─> backtest_daytrading
       └─> Simulate trades
       └─> Calculate metrics

7. Deployment
   └─> Model auto-loads from artifacts/
   └─> Trading engine uses latest model
```

---

## Quick Decision Tree

**Want to retrain?**
- Yes → Do you have 60+ days of DaySymbol data?
  - Yes → Do DaySymbols have RSI/MACD?
    - Yes → Generate features → Update labels → Train
    - No → Run `calculate_technical_indicators` first
  - No → Collect more data first

**Backtest looks bad?**
- Check data quality (RSI/MACD populated?)
- Try longer training period (90+ days)
- Check for data gaps
- Review feature engineering

**Model predicting same values?**
- Check target distribution (should have variance)
- Increase training data
- Adjust hyperparameters in modeling.py

---

For detailed explanations, see [RETRAINING_GUIDE.md](RETRAINING_GUIDE.md)
