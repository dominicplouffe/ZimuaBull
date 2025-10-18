# Automated Day Trading Model Retraining

This guide explains how to use the automated retraining command that handles the entire pipeline for you.

## Quick Start

### Standard Retraining (Recommended)
```bash
# Automatically detect what needs updating and retrain
.venv/bin/python manage.py retrain_daytrading_model
```

This will:
1. ✅ Find the last feature snapshot date
2. ✅ Generate features from that date to today
3. ✅ Update labels for completed trading days
4. ✅ Calculate missing technical indicators
5. ✅ Train the model on last 90 days
6. ✅ Run backtest validation on last 30 days
7. ✅ Save the new model

**Time estimate**: 10-30 minutes (depending on how many new days need processing)

---

## Usage Patterns

### Weekly Retraining (Every Monday)
```bash
# Standard incremental update
.venv/bin/python manage.py retrain_daytrading_model
```

This is smart:
- Only generates features for new days since last run
- Updates labels for newly completed trading days
- Trains on last 90 days (rolling window)
- Quick if you run it regularly

### Full Rebuild (Monthly or After Data Issues)
```bash
# Regenerate ALL features and retrain from scratch
.venv/bin/python manage.py retrain_daytrading_model --full-rebuild
```

Use this when:
- You fixed data quality issues
- You changed feature engineering logic
- You want to ensure everything is fresh
- First time setting up

### Bump Version and Rebuild
```bash
# Increment version (v2 -> v3) and rebuild everything
.venv/bin/python manage.py retrain_daytrading_model --bump-version
```

Use this when:
- You modified feature engineering code
- You want to test new features alongside old ones
- You're making breaking changes to the model

**What it does:**
- Changes `v2` → `v3` in `constants.py`
- Updates model filenames (`intraday_model_v3.joblib`)
- Regenerates all features with new version
- Trains new model
- Old v2 model remains available as fallback

---

## Command Options

### Exchange Selection
```bash
# Process only NASDAQ (default)
.venv/bin/python manage.py retrain_daytrading_model --exchange NASDAQ

# Process NYSE
.venv/bin/python manage.py retrain_daytrading_model --exchange NYSE

# Process TSE (Toronto)
.venv/bin/python manage.py retrain_daytrading_model --exchange TSE
```

### Training Window
```bash
# Use 120 days of training data (default: 90)
.venv/bin/python manage.py retrain_daytrading_model --training-days 120

# Use only 60 days (faster, but less data)
.venv/bin/python manage.py retrain_daytrading_model --training-days 60
```

### Backtest Window
```bash
# Test on last 60 days instead of 30
.venv/bin/python manage.py retrain_daytrading_model --backtest-days 60

# Skip backtest entirely (faster)
.venv/bin/python manage.py retrain_daytrading_model --skip-backtest
```

### Skip Steps
```bash
# Skip technical indicator calculation (if already done)
.venv/bin/python manage.py retrain_daytrading_model --skip-indicators

# Skip backtest (train only)
.venv/bin/python manage.py retrain_daytrading_model --skip-backtest

# Both
.venv/bin/python manage.py retrain_daytrading_model --skip-indicators --skip-backtest
```

### Minimum Training Samples
```bash
# Require at least 1000 samples (default: 500)
.venv/bin/python manage.py retrain_daytrading_model --min-rows 1000
```

---

## Example Output

```
================================================================================
🤖 AUTOMATED DAY TRADING MODEL RETRAINING
================================================================================

Exchange: NASDAQ
Training window: 90 days
Backtest window: 30 days
Current feature version: v2

================================================================================
📋 STEP 1: VERIFYING PREREQUISITES
================================================================================
✓ Found 3,247 symbols for NASDAQ
✓ Found 22,729 recent DaySymbol records (last 7 days)
✓ Technical indicators: 22,184/22,729 (97.6%) with RSI

================================================================================
📊 STEP 2: CALCULATING TECHNICAL INDICATORS
================================================================================
Calculating technical indicators for NASDAQ...
   Processed 50/3247 symbols, 432 records updated
   Processed 100/3247 symbols, 891 records updated
   ...
✓ Updated 545 records across 128 symbols

================================================================================
📅 STEP 3: DETERMINING FEATURE GENERATION RANGE
================================================================================
Incremental mode: Last snapshot found for 2025-10-15
Will generate features from 2025-10-16 to 2025-10-18

================================================================================
🔧 STEP 4: GENERATING FEATURES
================================================================================
Generating features for 3,247 symbols from 2025-10-16 to 2025-10-18...
Total trading days to process: 3
[1/3] 2025-10-16 | Day: 2,847 snapshots | Total: 2,847 | Progress: 33.3% | Speed: 15.2 days/min | ETA: 8s
[2/3] 2025-10-17 | Day: 2,853 snapshots | Total: 5,700 | Progress: 66.7% | Speed: 14.8 days/min | ETA: 4s
[3/3] 2025-10-18 | Day: 2,856 snapshots | Total: 8,556 | Progress: 100.0% | Speed: 14.5 days/min | ETA: 0s
✓ Generated 8,556 feature snapshots in 12s

================================================================================
🏷️  STEP 5: UPDATING LABELS
================================================================================
Updating labels from 2025-10-16 to 2025-10-17...
   2025-10-16: Updated 2847 labels (total: 2,847)
✓ Updated 2,847 labels
✓ Label coverage: 2,847/8,556 (33.3%)

================================================================================
🤖 STEP 6: TRAINING MODEL
================================================================================
Loading dataset from 2025-07-20 to 2025-10-18...
✓ Loaded 84,523 samples with 42 features

Training HistGradientBoostingRegressor...
   • Using TimeSeriesSplit cross-validation (prevents data leakage)
   • This may take 2-10 minutes depending on dataset size...

✓ Training complete!

📈 Cross-Validation Metrics:
   • R² Score:  0.0891 (±0.0134)
   • MAE Score: 0.0128 (±0.0009)
   • Samples:   84,523
   • Features:  42

💡 Interpretation:
   ✓ Good R² for intraday prediction
   ✓ Good MAE (<1.5% average error)

💾 Saving model...
✓ Model saved to: artifacts/daytrading/intraday_model_v2.joblib

================================================================================
📈 STEP 7: RUNNING BACKTEST VALIDATION
================================================================================
Loading backtest dataset from 2025-09-18 to 2025-10-18...
✓ Loaded 9,432 samples for backtesting

Running backtest simulation...

✓ Backtest complete!

============================================================
📈 BACKTEST RESULTS
============================================================

💰 Capital:
   Starting:   $  10,000.00
   Ending:     $  11,234.56
   Profit:     $   1,234.56

📊 Returns:
   Total Return:          12.35%
   Annualized Return:     52.41%

⚠️  Risk:
   Max Drawdown:           8.23%
   Sharpe Ratio:           1.84

🎯 Trading:
   Win Rate:              54.20%
   Total Trades:             142

============================================================

🎉 EXCELLENT BACKTEST!

================================================================================
✅ RETRAINING COMPLETE!
================================================================================

📝 Summary:
   • Feature Version: v2
   • Training Samples: 84,523
   • Features: 42
   • R² Score: 0.0891 (±0.0134)
   • MAE Score: 0.0128 (±0.0009)
   • Trained At: 2025-10-18T14:32:11.547291+00:00

🎯 Next Steps:
   1. Review backtest results above
   2. If metrics look good, model is ready for paper trading
   3. Monitor performance for 2-4 weeks before going live
   4. Retrain weekly to keep model fresh

✅ Automated retraining pipeline complete!
```

---

## Automation

### Weekly Cron Job (Recommended)
```bash
# Add to crontab: Every Sunday at 2 AM
0 2 * * 0 cd /path/to/ZimuaBull && .venv/bin/python manage.py retrain_daytrading_model >> /var/log/zimuabull/retrain.log 2>&1
```

### Celery Beat Task
```python
# In core/settings.py CELERY_BEAT_SCHEDULE
'retrain-daytrading-model': {
    'task': 'zimuabull.tasks.retrain_daytrading_model',
    'schedule': crontab(hour=2, minute=0, day_of_week=0),  # Sunday 2 AM
},
```

---

## What the Command Does Automatically

### 1. Smart Date Detection
- Finds your last feature snapshot
- Only processes new days (incremental)
- Ensures you have enough training history
- Skips weekends automatically

### 2. Technical Indicators
- Checks if RSI/MACD are missing
- Calculates only what's needed
- Shows progress for large batches

### 3. Feature Generation
- Creates feature snapshots for new days
- Shows real-time progress with ETA
- Handles errors gracefully

### 4. Label Updates
- Only labels completed trading days
- Can't label today (needs tomorrow's data)
- Shows coverage percentage

### 5. Model Training
- Uses proper time-series cross-validation
- Prevents data leakage
- Shows interpretable metrics
- Auto-saves to artifacts/

### 6. Backtest Validation
- Simulates actual trading
- Shows risk-adjusted returns
- Provides quality assessment
- Color-coded for easy reading

---

## Version Bumping

When you bump the version:

### Before (v2):
```python
# constants.py
FEATURE_VERSION = "v2"
MODEL_FILENAME = "intraday_model_v2.joblib"
MODEL_METADATA_FILENAME = "intraday_model_v2_meta.json"
```

### After (v3):
```python
# constants.py
# - v3: Automated retrain (2025-10-18)
FEATURE_VERSION = "v3"
MODEL_FILENAME = "intraday_model_v3.joblib"
MODEL_METADATA_FILENAME = "intraday_model_v3_meta.json"
```

### File Structure:
```
artifacts/daytrading/
├── intraday_model_v2.joblib          # Old model (kept)
├── intraday_model_v2_meta.json       # Old metadata (kept)
├── intraday_model_v3.joblib          # New model
└── intraday_model_v3_meta.json       # New metadata
```

**Benefits:**
- Keep old versions as fallback
- A/B test new features
- Easy rollback if needed
- Clear version history

---

## Troubleshooting

### "No symbols found for exchange"
**Problem**: Exchange doesn't have symbols in database.

**Solution**: Check exchange code or populate symbols first.
```bash
.venv/bin/python manage.py shell -c "
from zimuabull.models import Symbol
print(Symbol.objects.values('exchange__code').distinct())
"
```

### "No recent DaySymbol data"
**Problem**: No stock data collected recently.

**Solution**: Run your data collection process first (scanner tasks).

### "Insufficient training samples"
**Problem**: Not enough labeled feature snapshots.

**Solution**: Extend training window or do full rebuild.
```bash
.venv/bin/python manage.py retrain_daytrading_model --training-days 120
```

### "Low RSI coverage"
**Problem**: Many DaySymbol records missing technical indicators.

**Solution**: Command will automatically calculate them. Or run manually:
```bash
.venv/bin/python manage.py calculate_technical_indicators --force
```

### Command takes too long
**Solutions**:
1. Run incrementally more often (weekly instead of monthly)
2. Skip backtest: `--skip-backtest`
3. Reduce training window: `--training-days 60`
4. Process specific exchange: `--exchange NASDAQ`

### Poor backtest results
**Check**:
1. Data quality (RSI/MACD populated?)
2. Training window (need 60-90 days minimum)
3. Model metrics (R² should be > 0.05)
4. Market conditions (backtest period representative?)

**Solutions**:
1. Full rebuild: `--full-rebuild`
2. More training data: `--training-days 120`
3. Check feature engineering logic
4. Review model hyperparameters in `modeling.py`

---

## Comparison: Manual vs Automated

### Manual Process (Old Way)
```bash
# 1. Calculate indicators
.venv/bin/python manage.py calculate_technical_indicators

# 2. Generate features
.venv/bin/python manage.py generate_daytrading_features \
  --start-date 2025-07-20 --end-date 2025-10-18 --exchange NASDAQ

# 3. Update labels (loop through dates)
for day in 14 15 16 17 18; do
  .venv/bin/python manage.py update_daytrading_labels --date 2025-10-$day
done

# 4. Train
.venv/bin/python manage.py train_daytrading_model

# 5. Backtest
.venv/bin/python manage.py backtest_daytrading \
  --start-date 2025-09-18 --end-date 2025-10-18

# 6. Check results manually
```

**Time**: 30-60 minutes (manual work)
**Error-prone**: Must specify correct dates, easy to forget steps

### Automated Process (New Way)
```bash
.venv/bin/python manage.py retrain_daytrading_model
```

**Time**: 10-30 minutes (fully automated)
**Reliable**: Handles all steps automatically, smart date detection

---

## Integration with Weekly Review

Combine with portfolio review for complete automation:

```bash
# Sunday 2 AM: Retrain model
0 2 * * 0 cd /path/to/ZimuaBull && .venv/bin/python manage.py retrain_daytrading_model

# Sunday 3 AM: Generate weekly report
0 3 * * 0 cd /path/to/ZimuaBull && .venv/bin/python manage.py weekly_portfolio_review
```

This gives you:
1. Fresh model every week
2. Performance review and recommendations
3. Complete automation of the learning loop

---

## Best Practices

1. **Run Weekly**: Retrain every Sunday after market close Friday
2. **Monitor Logs**: Save output to log file for review
3. **Check Metrics**: Review R² and backtest results before deploying
4. **Paper Trade First**: Test new model for 1-2 weeks before live trading
5. **Keep Versions**: Don't delete old model files immediately
6. **Validate Data**: Ensure data collection ran successfully before retraining

---

## Next Steps

1. **Test the command**:
   ```bash
   .venv/bin/python manage.py retrain_daytrading_model --help
   ```

2. **Do a test run**:
   ```bash
   .venv/bin/python manage.py retrain_daytrading_model --skip-backtest
   ```

3. **Review output** and check metrics

4. **Set up automation** with cron or Celery Beat

5. **Monitor weekly** and adjust parameters as needed

---

For detailed information about the underlying process, see [RETRAINING_GUIDE.md](RETRAINING_GUIDE.md)

For quick command reference, see [RETRAINING_CHEATSHEET.md](RETRAINING_CHEATSHEET.md)
