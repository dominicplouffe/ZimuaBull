# Deprecated Management Commands

These commands have been superseded by the automated `retrain_daytrading_model` command.

## Why Deprecated?

The new automated command (`retrain_daytrading_model`) handles the entire retraining pipeline in one step:
- Automatically detects what needs updating
- Generates features incrementally
- Updates labels for completed days
- Calculates technical indicators if needed
- Trains the model
- Runs backtest validation

**Old way (5+ commands):**
```bash
.venv/bin/python manage.py calculate_technical_indicators
.venv/bin/python manage.py generate_daytrading_features --start-date ... --end-date ...
for day in ...; do .venv/bin/python manage.py update_daytrading_labels --date ...; done
.venv/bin/python manage.py train_daytrading_model
.venv/bin/python manage.py backtest_daytrading --start-date ... --end-date ...
```

**New way (1 command):**
```bash
.venv/bin/python manage.py retrain_daytrading_model
```

## Commands Moved Here

1. **calculate_technical_indicators.py** - Calculate RSI, MACD for DaySymbol records
2. **generate_daytrading_features.py** - Generate FeatureSnapshot records
3. **update_daytrading_labels.py** - Update labels for completed trading days
4. **train_daytrading_model.py** - Train the ML model
5. **backtest_daytrading.py** - Run backtest validation

## Should You Use These?

**No** - Use `retrain_daytrading_model` instead. It's:
- ✅ Smarter (auto-detects what to update)
- ✅ Faster (incremental updates)
- ✅ Safer (proper validation)
- ✅ Easier (one command)

## When These Might Be Useful

**Debugging specific steps:**
- If you need to test feature generation logic in isolation
- If you need to recalculate indicators for specific symbols only
- If you're developing new features

**To use a deprecated command:**
```bash
# Copy it back to the main commands folder temporarily
cp zimuabull/management/commands/deprecated/calculate_technical_indicators.py zimuabull/management/commands/

# Use it
.venv/bin/python manage.py calculate_technical_indicators

# Remove it when done
rm zimuabull/management/commands/calculate_technical_indicators.py
```

## Kept for Reference

These files are kept for:
1. Reference implementation
2. Debugging individual pipeline steps
3. Understanding how each step works
4. Potential future refactoring

## Migration Date

Deprecated: 2025-10-18
Replaced by: `retrain_daytrading_model.py`
