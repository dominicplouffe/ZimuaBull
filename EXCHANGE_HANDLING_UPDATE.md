# Exchange Handling Update - retrain_daytrading_model

## Issue

The `retrain_daytrading_model` command was defaulting to **NASDAQ only**, which meant it would only process NASDAQ symbols and not other exchanges like NYSE or TSE.

## Fix

Updated the command to **default to ALL exchanges** instead of just NASDAQ.

### Before
```bash
# Only processed NASDAQ (default)
python manage.py retrain_daytrading_model

# Had to explicitly specify for other exchanges
python manage.py retrain_daytrading_model --exchange NYSE
```

### After
```bash
# Now processes ALL exchanges by default
python manage.py retrain_daytrading_model

# Can still specify specific exchange if needed
python manage.py retrain_daytrading_model --exchange NASDAQ
python manage.py retrain_daytrading_model --exchange NYSE
python manage.py retrain_daytrading_model --exchange TSE
```

## Usage

### All Exchanges (New Default)
```bash
# Process all exchanges - NASDAQ, NYSE, TSE, etc.
python manage.py retrain_daytrading_model
```

**Output:**
```
Exchange: ALL
✓ Found 5,432 symbols across 3 exchanges:
    - NASDAQ: 3,247 symbols
    - NYSE: 2,145 symbols
    - TSE: 40 symbols
```

### Specific Exchange
```bash
# Only NASDAQ
python manage.py retrain_daytrading_model --exchange NASDAQ

# Only NYSE
python manage.py retrain_daytrading_model --exchange NYSE

# Only TSE (Toronto)
python manage.py retrain_daytrading_model --exchange TSE
```

**Output:**
```
Exchange: NASDAQ
✓ Found 3,247 symbols for NASDAQ
```

## Benefits

### More Comprehensive Training
- Model learns from all available market data
- Better generalization across different exchanges
- Captures cross-market patterns

### Saves Time
- One command trains on everything
- No need to run separate commands per exchange
- Automatic discovery of all exchanges in your database

### Flexibility
- Still supports single-exchange training if needed
- Useful for debugging specific exchanges
- Can limit scope for faster testing

## Technical Changes

Updated the following methods to handle `exchange=None` (all exchanges):

1. **`_verify_prerequisites`** - Shows breakdown by exchange
2. **`_calculate_indicators`** - Processes all exchanges
3. **`_determine_date_range`** - Finds latest snapshot across all exchanges
4. **`_generate_features`** - Generates features for all symbols
5. **`_update_labels`** - Updates labels for all exchanges

## Migration

### If You Were Using Default Behavior

**Before (implicitly NASDAQ only):**
```bash
python manage.py retrain_daytrading_model
# Only trained on NASDAQ
```

**After (now all exchanges):**
```bash
python manage.py retrain_daytrading_model
# Trains on ALL exchanges
```

**To restore old behavior** (NASDAQ only):
```bash
python manage.py retrain_daytrading_model --exchange NASDAQ
```

### If You Were Specifying Exchange

No changes needed! Explicitly specifying exchange still works:
```bash
python manage.py retrain_daytrading_model --exchange NASDAQ  # Still works
python manage.py retrain_daytrading_model --exchange NYSE    # Still works
```

## Examples

### Weekly Automated Retraining (All Exchanges)
```bash
# Cron job: Sunday 2 AM, train on all exchanges
0 2 * * 0 cd /path/to/ZimuaBull && .venv/bin/python manage.py retrain_daytrading_model
```

### Test Single Exchange
```bash
# Quick test on just NASDAQ
python manage.py retrain_daytrading_model --exchange NASDAQ --skip-backtest
```

### Full Rebuild All Exchanges
```bash
# Regenerate everything for all exchanges
python manage.py retrain_daytrading_model --full-rebuild
```

## Performance Impact

### Training Time
- **All exchanges**: Longer (more symbols, more features)
- **Single exchange**: Faster (fewer symbols)

**Example**:
- NASDAQ only: ~15 minutes
- NYSE only: ~10 minutes
- All exchanges: ~30 minutes

### Model Quality
- **All exchanges**: Better generalization, more training data
- **Single exchange**: Faster, but potentially less robust

**Recommendation**: Use all exchanges for production, single exchange for testing.

## Best Practices

### Production (Recommended)
```bash
# Weekly retraining on all exchanges
python manage.py retrain_daytrading_model
```

### Development/Testing
```bash
# Quick iteration on one exchange
python manage.py retrain_daytrading_model --exchange NASDAQ --skip-backtest
```

### Exchange-Specific Models
If you want separate models per exchange:
```bash
# Monday: NASDAQ model
python manage.py retrain_daytrading_model --exchange NASDAQ

# Tuesday: NYSE model
python manage.py retrain_daytrading_model --exchange NYSE

# etc.
```

Note: This creates ONE model trained on the specified exchange. The system doesn't support multiple models simultaneously (yet).

## Questions & Answers

**Q: Will this use more memory?**
A: Yes, processing more symbols uses more memory. If you have memory constraints, train on single exchanges.

**Q: Can I exclude specific exchanges?**
A: Not currently. You can either:
- Train on all exchanges
- Train on one specific exchange

**Q: Does the model differentiate between exchanges?**
A: Yes! The `exchange_code` is a feature in the model, so it learns exchange-specific patterns.

**Q: Should I use all exchanges or just one?**
A: Depends:
- **All exchanges** = Better generalization, more robust
- **Single exchange** = Faster, exchange-specific optimization

For most users: **Use all exchanges**.

## Future Enhancements

Potential improvements:
1. **Multi-model support**: Separate models per exchange
2. **Exchange filtering**: `--exclude NYSE` or `--include NASDAQ,NYSE`
3. **Parallel processing**: Train exchanges simultaneously
4. **Exchange weighting**: Give more weight to certain exchanges

---

**Date**: October 18, 2025
**Updated by**: Claude Code
**Impact**: Behavior change - default changed from NASDAQ-only to all exchanges
