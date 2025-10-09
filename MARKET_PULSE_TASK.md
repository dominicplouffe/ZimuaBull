# Market Pulse Update Task

## Overview
A unified Celery task that updates both portfolio symbol prices and market indices every 5 minutes during trading hours.

## What It Does

### 1. Portfolio Symbol Price Updates
- Fetches live prices for all symbols in user portfolios
- Updates `Symbol.latest_price` and `Symbol.price_updated_at`
- Updates `PortfolioHolding.current_price` and `PortfolioHolding.total_value`
- Handles multiple exchanges (TSE, NASDAQ, NYSE)

### 2. Market Index Updates
- Updates major market indices (S&P 500, NASDAQ Composite, TSX Composite, etc.)
- Creates/updates `MarketIndexData` records
- Tracks OHLCV data for indices

### 3. Smart Execution
- **Only runs during market hours** to avoid unnecessary API calls
- Checks if TSE, NASDAQ, or NYSE are open before executing
- Skips execution if all markets are closed
- Returns comprehensive reports of all updates

## Schedule

**Runs every 5 minutes** (configured in `core/settings.py`)

```python
CELERY_BEAT_SCHEDULE = {
    "zimuabull.tasks.portfolio_price_update.market_pulse_update": {
        "task": "zimuabull.tasks.portfolio_price_update.market_pulse_update",
        "schedule": crontab(minute='*/5'),  # Every 5 minutes
        "options": {"queue": "pidashtasks"},
    },
}
```

## Market Hours Detection

The task automatically detects market hours for:
- **TSE/TO** (Toronto): 9:30 AM - 4:00 PM ET (Monday-Friday)
- **NYSE**: 9:30 AM - 4:00 PM ET (Monday-Friday)
- **NASDAQ**: 9:30 AM - 4:00 PM ET (Monday-Friday)

## Task Location

File: [`zimuabull/tasks/portfolio_price_update.py`](zimuabull/tasks/portfolio_price_update.py)

### Main Functions

1. **`market_pulse_update()`** - Main scheduled task (Celery shared_task)
2. **`update_portfolio_symbols_prices()`** - Updates portfolio holdings
3. **`update_market_indices()`** - Updates market index data
4. **`is_market_open(exchange_code)`** - Checks if market is currently open

## Testing

### Manual Test via Management Command

```bash
python manage.py test_market_pulse
```

This will:
- Run the task immediately
- Display a formatted summary
- Show success/failure counts
- Display market open/closed status

### Manual Test via Python Shell

```bash
python manage.py shell
```

```python
from zimuabull.tasks.portfolio_price_update import market_pulse_update

# Run the task
result = market_pulse_update()

# View results
print(result)
```

### Celery Task Invocation

```bash
# If Celery worker is running, you can trigger manually:
celery -A core call zimuabull.tasks.portfolio_price_update.market_pulse_update
```

## Return Value

The task returns a comprehensive report:

```json
{
  "status": "completed",
  "timestamp": "2025-10-09T14:35:00Z",
  "market_status": {
    "TSE": true,
    "NASDAQ": true,
    "NYSE": true
  },
  "portfolio_updates": {
    "successful": 15,
    "failed": 0,
    "details": {
      "total_portfolios": 3,
      "market_status": {...},
      "successful_updates": ["SHOP (TSE): $125.50", ...],
      "failed_updates": []
    }
  },
  "index_updates": {
    "successful": 3,
    "failed": 0,
    "details": {
      "updated": ["^GSPTSE: $21234.56", "^GSPC: $4567.89", "^IXIC: $14234.56"],
      "failed": []
    }
  }
}
```

### When Markets Are Closed

```json
{
  "status": "skipped",
  "reason": "All markets closed",
  "market_status": {
    "TSE": false,
    "NASDAQ": false,
    "NYSE": false
  },
  "timestamp": "2025-10-09T02:00:00Z"
}
```

## Starting Celery Services

### Start Celery Worker

```bash
celery -A core worker -l info -Q pidashtasks
```

### Start Celery Beat (Scheduler)

```bash
celery -A core beat -l info
```

### Or Both Together (Development)

```bash
celery -A core worker -l info -Q pidashtasks --beat
```

## Monitoring

### View Scheduled Tasks

```bash
# Django admin -> Periodic Tasks (if using django-celery-beat)
# Or check logs from celery beat
```

### Check Last Execution

```python
from django_celery_beat.models import PeriodicTask

task = PeriodicTask.objects.get(name='zimuabull.tasks.portfolio_price_update.market_pulse_update')
print(f"Last run: {task.last_run_at}")
print(f"Total runs: {task.total_run_count}")
```

## Configuration

### Modify Schedule

Edit [`core/settings.py`](core/settings.py):

```python
# Change frequency (e.g., every 10 minutes instead of 5)
"schedule": crontab(minute='*/10'),

# Run only during specific hours (e.g., 9 AM - 5 PM)
"schedule": crontab(minute='*/5', hour='9-17'),

# Run on specific days (e.g., weekdays only)
"schedule": crontab(minute='*/5', day_of_week='1-5'),
```

### Add More Exchanges

Edit [`zimuabull/tasks/portfolio_price_update.py`](zimuabull/tasks/portfolio_price_update.py):

```python
# In market_pulse_update() function
major_exchanges = ['TSE', 'NASDAQ', 'NYSE', 'LSE']  # Add London Stock Exchange
```

## Dependencies

- **yfinance**: Fetches live price data from Yahoo Finance
- **celery**: Task queue
- **redis**: Celery broker
- **django-celery-beat**: Database-backed periodic tasks

## Notes

- The task uses Yahoo Finance (`yfinance`) which has rate limits
- TSE tickers are automatically converted (e.g., `SHOP` → `SHOP.TO`)
- Prices are cached in the database to reduce API calls
- The task is idempotent - safe to run multiple times
- Failed updates are logged but don't stop the entire task

## Troubleshooting

### Task Not Running

1. Check Celery beat is running: `ps aux | grep celery`
2. Check Redis is running: `redis-cli ping`
3. Check logs: `tail -f celery.log`

### Prices Not Updating

1. Check market hours: Markets must be open
2. Verify yfinance is installed: `pip list | grep yfinance`
3. Check symbol exists in database
4. Test manually: `python manage.py test_market_pulse`

### Yahoo Finance API Errors

- Yahoo Finance occasionally changes their API
- Update yfinance: `pip install --upgrade yfinance`
- Check yfinance GitHub for known issues
