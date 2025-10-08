# Setup Guide for New LLM Features

This guide covers setting up the newly implemented LLM features for ZimuaBull.

## 1. Database Migrations

Run migrations to create new tables and fields:

```bash
python manage.py makemigrations
python manage.py migrate
```

**New tables created:**
- `SignalHistory` - Tracks trading signal changes over time
- `MarketIndex` - Major market indices (S&P 500, NASDAQ, etc.)
- `MarketIndexData` - Daily data for market indices

**New fields added:**
- `Symbol.sector` - Stock sector (e.g., "Technology")
- `Symbol.industry` - Stock industry (e.g., "Software")
- `DaySymbol.rsi` - Relative Strength Index (0-100)
- `DaySymbol.macd` - MACD line value
- `DaySymbol.macd_signal` - MACD signal line value
- `DaySymbol.macd_histogram` - MACD histogram value

## 2. Calculate RSI/MACD for Existing Data

Calculate technical indicators for all existing DaySymbol records:

```bash
# Calculate for all symbols (may take a while)
python manage.py calculate_technical_indicators

# Or calculate for specific symbol
python manage.py calculate_technical_indicators --symbol AAPL --exchange NASDAQ

# Force recalculation even if values exist
python manage.py calculate_technical_indicators --force
```

**Note:** This needs at least:
- 14 days of data for RSI
- 35 days of data for MACD (26 slow + 9 signal)

## 3. Populate Market Indices

Create market index records and fetch their historical data:

```bash
# Step 1: Create index records (S&P 500, NASDAQ, etc.)
python manage.py populate_market_indices --create-indices

# Step 2: Fetch historical data (requires yfinance)
pip install yfinance
# Then uncomment the code in the management command and run:
python manage.py populate_market_indices --fetch-data --days 365
```

**Default indices created:**
- S&P 500 (^GSPC)
- NASDAQ Composite (^IXIC)
- Dow Jones (^DJI)
- S&P/TSX Composite (^GSPTSE)
- Russell 2000 (^RUT)

## 4. Populate Sector/Industry Data

Populate sector and industry fields for symbols:

```bash
# Install yfinance for automatic population
pip install yfinance

# Then uncomment the code in the management command and run:
python manage.py populate_sectors

# Or populate manually via Django shell:
python manage.py shell
>>> from zimuabull.models import Symbol
>>> symbol = Symbol.objects.get(symbol='AAPL')
>>> symbol.sector = 'Technology'
>>> symbol.industry = 'Consumer Electronics'
>>> symbol.save()
```

## 5. Automated Signal Tracking

Signal changes are now automatically tracked when `process_symbol_data` runs.

The task will create `SignalHistory` records whenever a symbol's trading signal changes (e.g., from BUY to HOLD).

No manual action needed - this runs during daily stock processing.

## 6. New API Endpoints

All new endpoints are now available:

### Backtesting
```bash
# What if I bought AAPL 30 days ago?
GET /api/backtest/?symbol=AAPL&exchange=NASDAQ&days_ago=30&strategy=buy_hold&investment=10000

# What if I followed trading signals?
GET /api/backtest/?symbol=AAPL&exchange=NASDAQ&days_ago=90&strategy=signal_follow
```

### Market Benchmarks
```bash
# Get S&P 500 and NASDAQ performance
GET /api/market-benchmarks/?indices=^GSPC,^IXIC&days=30
```

### Compare Multiple Symbols
```bash
# Compare up to 10 symbols with historical data
GET /api/compare-symbols/?symbols=AAPL:NASDAQ,MSFT:NASDAQ,GOOGL:NASDAQ&include_history=true
```

### LLM Context with Technical Indicators
```bash
# Get full context including RSI/MACD
GET /api/llm-context/?symbol=AAPL&exchange=NASDAQ&include_history=true&history_days=30
```

## 7. What LLM Can Now Answer

With these features, your LLM integration can answer:

✅ **Technical Analysis:**
- "What is the RSI for AAPL?" → Uses DaySymbol.rsi
- "Is TSLA overbought?" → RSI > 70 = overbought
- "Show me MACD for MSFT" → MACD indicator values

✅ **Historical What-If:**
- "What if I bought AAPL 30 days ago?" → Backtesting endpoint
- "How would signal-following perform?" → strategy=signal_follow

✅ **Market Comparison:**
- "How does AAPL compare to S&P 500?" → Market benchmarks
- "Compare AAPL vs MSFT vs GOOGL" → Compare symbols endpoint

✅ **Signal History:**
- "When did the signal last change?" → SignalHistory model
- "How reliable are BUY signals?" → Track signal history accuracy

✅ **Moving Averages:**
- "Calculate 15-day moving average" → Historical OHLCV data
- "Show me 50-day and 200-day MA" → Historical data calculations

## 8. Optional: Django Admin

Register new models in Django admin for easy viewing:

Add to `zimuabull/admin.py`:
```python
from django.contrib import admin
from .models import SignalHistory, MarketIndex, MarketIndexData

@admin.register(SignalHistory)
class SignalHistoryAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'date', 'previous_signal', 'new_signal', 'price']
    list_filter = ['new_signal', 'previous_signal', 'date']
    search_fields = ['symbol__symbol']

@admin.register(MarketIndex)
class MarketIndexAdmin(admin.ModelAdmin):
    list_display = ['name', 'symbol', 'country']
    search_fields = ['name', 'symbol']

@admin.register(MarketIndexData)
class MarketIndexDataAdmin(admin.ModelAdmin):
    list_display = ['index', 'date', 'close', 'volume']
    list_filter = ['index', 'date']
```

## 9. Testing

Test the new endpoints:

```bash
# Test RSI/MACD calculation
curl "http://localhost:8000/api/llm-context/?symbol=AAPL&exchange=NASDAQ&include_history=true"

# Test backtesting
curl "http://localhost:8000/api/backtest/?symbol=AAPL&exchange=NASDAQ&days_ago=30"

# Test market benchmarks
curl "http://localhost:8000/api/market-benchmarks/?indices=^GSPC"

# Test symbol comparison
curl "http://localhost:8000/api/compare-symbols/?symbols=AAPL:NASDAQ,MSFT:NASDAQ"
```

## Summary Checklist

- [ ] Run `makemigrations` and `migrate`
- [ ] Run `calculate_technical_indicators` for RSI/MACD
- [ ] Run `populate_market_indices --create-indices`
- [ ] Install `yfinance` and fetch market index data
- [ ] Populate sector/industry data (optional but recommended)
- [ ] Test new API endpoints
- [ ] Update frontend to use new features

## Notes

- RSI/MACD calculation is computationally intensive - consider running overnight for large datasets
- Market index data fetching requires yfinance library
- Signal history tracking is automatic going forward
- Sector/industry data improves LLM responses but is optional
