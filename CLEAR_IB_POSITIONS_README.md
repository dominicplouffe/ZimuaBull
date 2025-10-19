# Clear IB Positions Script

## Overview

`clear_ib_positions.py` is a utility script that clears all positions from your Interactive Brokers (IB) paper trading account by submitting SELL market orders for each holding.

## Features

- ✅ Connects to IB Gateway/TWS using portfolio configuration
- ✅ Fetches all current positions from IB account
- ✅ Submits SELL market orders for each position
- ✅ Tracks order status and confirmations
- ✅ Handles symbol lookup/creation automatically
- ✅ Supports dry-run mode for testing
- ✅ Comprehensive logging

## Prerequisites

1. **IB Gateway or TWS must be running**
   - Paper trading mode enabled
   - API connections enabled in settings
   - Correct port configured (typically 7497 for paper trading)

2. **Portfolio configured in database**
   - `use_interactive_brokers = True`
   - `ib_host`, `ib_port`, `ib_client_id` configured
   - `ib_account` set (if using multiple accounts)

## Usage

### Basic Usage

```bash
# Clear all positions (will prompt for confirmation)
python clear_ib_positions.py --portfolio-id 1
```

### Dry Run (Test Mode)

```bash
# See what would be done without actually submitting orders
python clear_ib_positions.py --portfolio-id 1 --dry-run
```

### With Virtual Environment

```bash
.venv/bin/python clear_ib_positions.py --portfolio-id 1
```

## How It Works

1. **Connect to IB**
   - Uses portfolio configuration to connect to IB Gateway/TWS
   - Validates connection and configuration

2. **Fetch Positions**
   - Calls `ib.positions()` to get all current holdings
   - Displays symbol, quantity, and average cost for each position

3. **Submit SELL Orders**
   - For each position:
     - Looks up symbol in database (creates if needed)
     - Submits SELL market order for the full quantity
     - Logs order ID and status

4. **Monitor Orders**
   - Waits 30 seconds for orders to fill
   - Checks status every 5 seconds
   - Reports final status for each order

5. **Verify Completion**
   - Re-fetches positions from IB
   - Confirms account is cleared

## Example Output

```
================================================================================
IB POSITION CLEARER
================================================================================

2025-10-19 10:30:15 [INFO] Using portfolio: Paper Trading (ID: 1)
2025-10-19 10:30:15 [INFO] Connecting to IB at localhost:7497...
2025-10-19 10:30:16 [INFO] ✓ Connected to IB
2025-10-19 10:30:16 [INFO] Found 3 position(s) in IB account:
2025-10-19 10:30:16 [INFO]   - AAPL: 100 shares @ 175.50
2025-10-19 10:30:16 [INFO]   - MSFT: 50 shares @ 380.25
2025-10-19 10:30:16 [INFO]   - GOOGL: 25 shares @ 142.80

================================================================================
Submitting SELL orders for 3 position(s)...
================================================================================

2025-10-19 10:30:17 [INFO] Processing AAPL: 100 shares
2025-10-19 10:30:17 [INFO]   Submitting SELL market order for 100 shares of AAPL...
2025-10-19 10:30:17 [INFO]   ✓ Order submitted (Order ID: 12345)
2025-10-19 10:30:18 [INFO] Processing MSFT: 50 shares
2025-10-19 10:30:18 [INFO]   Submitting SELL market order for 50 shares of MSFT...
2025-10-19 10:30:18 [INFO]   ✓ Order submitted (Order ID: 12346)
2025-10-19 10:30:19 [INFO] Processing GOOGL: 25 shares
2025-10-19 10:30:19 [INFO]   Submitting SELL market order for 25 shares of GOOGL...
2025-10-19 10:30:19 [INFO]   ✓ Order submitted (Order ID: 12347)

================================================================================
Waiting for order confirmations (30 seconds)...
================================================================================

2025-10-19 10:30:25 [INFO] Checking order status... (5s)
2025-10-19 10:30:25 [INFO]   AAPL: Filled (100/100 filled)
2025-10-19 10:30:25 [INFO]   MSFT: Filled (50/50 filled)
2025-10-19 10:30:25 [INFO]   GOOGL: Filled (25/25 filled)

================================================================================
✓ All orders submitted successfully
================================================================================

2025-10-19 10:30:45 [INFO] No positions found in IB account
2025-10-19 10:30:45 [INFO] ✓ Account cleared - no positions remaining
2025-10-19 10:30:45 [INFO] Disconnected from IB

✓ Script completed successfully
```

## Dry Run Example

```bash
$ python clear_ib_positions.py --portfolio-id 1 --dry-run

================================================================================
IB POSITION CLEARER
================================================================================

⚠ DRY RUN MODE - No orders will be submitted

2025-10-19 10:35:00 [INFO] Found 3 position(s) in IB account:
2025-10-19 10:35:00 [INFO]   - AAPL: 100 shares @ 175.50
2025-10-19 10:35:00 [INFO]   - MSFT: 50 shares @ 380.25
2025-10-19 10:35:00 [INFO]   - GOOGL: 25 shares @ 142.80

2025-10-19 10:35:00 [INFO] Processing AAPL: 100 shares
2025-10-19 10:35:00 [INFO]   [DRY RUN] Would submit SELL market order for 100 shares of AAPL
2025-10-19 10:35:00 [INFO] Processing MSFT: 50 shares
2025-10-19 10:35:00 [INFO]   [DRY RUN] Would submit SELL market order for 50 shares of MSFT
2025-10-19 10:35:00 [INFO] Processing GOOGL: 25 shares
2025-10-19 10:35:00 [INFO]   [DRY RUN] Would submit SELL market order for 25 shares of GOOGL

================================================================================
DRY RUN COMPLETE - No orders were actually submitted
================================================================================
```

## Finding Your Portfolio ID

```bash
# List all portfolios
python manage.py shell -c "
from zimuabull.models import Portfolio
for p in Portfolio.objects.all():
    print(f'ID: {p.id}, Name: {p.name}, IB Enabled: {p.use_interactive_brokers}')
"
```

Or use the Django admin interface at `/admin/zimuabull/portfolio/`.

## Troubleshooting

### Connection Failed

**Error**: `Connection failed: [Errno 61] Connection refused`

**Solution**:
- Ensure IB Gateway or TWS is running
- Verify API connections are enabled in IB settings
- Check that the correct port is configured (7497 for paper, 7496 for live)
- Ensure `ib_host` and `ib_port` in portfolio match IB Gateway settings

### No Positions Found

**Error**: `No positions found in IB account`

**Solution**:
- This is normal if your account has no positions
- Verify you're connected to the correct account
- Check IB Gateway account dropdown

### Symbol Not Found

**Warning**: `Symbol AAPL not found in database. Creating minimal record.`

**Solution**:
- This is normal - the script will create a minimal symbol record
- Symbols will be automatically associated with the correct exchange
- To pre-populate symbols, run the scanner: `python manage.py scan_stocks`

### Order Submission Failed

**Error**: `Order submission failed: Invalid contract`

**Solution**:
- Contract may not be tradeable in paper trading
- Try using dry-run mode to see which symbols are problematic
- Check IB TWS for contract details

## Safety Features

1. **Dry Run Mode**: Test without submitting real orders
2. **Logging**: All actions logged with timestamps
3. **Error Handling**: Continues processing even if individual orders fail
4. **Confirmation**: Shows order status after submission
5. **Paper Trading**: Designed for paper accounts only

## Important Notes

⚠️ **This script submits MARKET orders** - execution price is not guaranteed

⚠️ **Paper trading only** - Do not use with live accounts without thorough testing

⚠️ **No rollback** - Once orders are submitted, you cannot undo them automatically

⚠️ **Settlement time** - It may take a few seconds for orders to fill in paper trading

## Related Files

- `zimuabull/daytrading/ib_connector.py` - IB connection management
- `zimuabull/models.py` - Portfolio and Symbol models
- `zimuabull/tasks/ib_order_monitor.py` - Order monitoring tasks

## Advanced Usage

### Clearing Specific Portfolio

```bash
# Clear positions for a specific portfolio
python clear_ib_positions.py --portfolio-id 2
```

### Automated Clearing

You could add this to a cron job or scheduled task:

```bash
# Clear positions daily at 4 PM ET (after market close)
0 16 * * 1-5 cd /path/to/ZimuaBull && .venv/bin/python clear_ib_positions.py --portfolio-id 1
```

### Integration with Django Management Command

You could convert this to a Django management command:

```python
# zimuabull/management/commands/clear_ib_positions.py
from django.core.management.base import BaseCommand
from clear_ib_positions import clear_all_positions

class Command(BaseCommand):
    help = "Clear all positions from IB paper trading account"

    def add_arguments(self, parser):
        parser.add_argument("--portfolio-id", type=int, required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        clear_all_positions(options["portfolio_id"], options["dry_run"])
```

Then run as:
```bash
python manage.py clear_ib_positions --portfolio-id 1
```
