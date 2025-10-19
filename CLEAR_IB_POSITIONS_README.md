# Clear IB Positions Script

## Overview

`clear_ib_positions.py` is a simple utility script that clears all positions from your Interactive Brokers (IB) paper trading account by submitting SELL market orders for each holding.

**This script connects directly to IB API - no database models or portfolio configuration required.**

## Features

- ✅ Direct connection to IB Gateway/TWS
- ✅ Fetches all current positions using `ib.positions()`
- ✅ Submits SELL market orders for each position
- ✅ Monitors order status for 30 seconds
- ✅ Verifies positions are cleared
- ✅ Supports dry-run mode for testing
- ✅ Simple standalone script - no Django models needed

## Prerequisites

1. **IB Gateway or TWS must be running**
   - Paper trading mode enabled
   - API connections enabled in settings (File → Global Configuration → API → Settings)
   - Correct port configured (7497 for paper trading by default)

2. **ib_insync library installed**
   ```bash
   pip install ib_insync
   ```

## Usage

### Basic Usage (Default Settings)

```bash
# Connect to localhost:7497 with client_id=1
python clear_ib_positions.py
```

### Dry Run (Test Mode)

```bash
# See what would be done without actually submitting orders
python clear_ib_positions.py --dry-run
```

### Custom Connection Settings

```bash
# Custom host, port, and client ID
python clear_ib_positions.py --host localhost --port 7497 --client-id 1

# Connect to TWS on different port
python clear_ib_positions.py --port 7496
```

### All Options

```bash
python clear_ib_positions.py --help

Options:
  --host HOST          IB Gateway/TWS host (default: localhost)
  --port PORT          IB Gateway/TWS port (default: 7497 for paper trading)
  --client-id ID       IB API client ID (default: 1)
  --dry-run            Show what would be done without submitting orders
```

## How It Works

1. **Connect to IB**
   - Connects to IB Gateway/TWS using specified host, port, and client ID
   - Default: `localhost:7497` with `client_id=1`

2. **Fetch Positions**
   - Calls `ib.positions()` to get all current holdings
   - Displays symbol, exchange, quantity, and average cost

3. **Submit SELL Orders**
   - For each position:
     - Creates SELL market order for full quantity
     - Submits order via `ib.placeOrder()`
     - Logs order ID

4. **Monitor Orders**
   - Checks order status every 5 seconds for 30 seconds
   - Reports fill status for each order

5. **Verify Completion**
   - Re-fetches positions from IB
   - Confirms account is cleared

## Example Output

```
================================================================================
IB POSITION CLEARER
================================================================================

2025-10-19 10:30:15 [INFO] Connecting to IB at localhost:7497 with client_id=1...
2025-10-19 10:30:16 [INFO] ✓ Connected to IB

2025-10-19 10:30:16 [INFO] Fetching current positions...
2025-10-19 10:30:16 [INFO] Found 3 position(s) in IB account:
2025-10-19 10:30:16 [INFO]   - AAPL (SMART): 100.0 shares @ avg cost 175.50
2025-10-19 10:30:16 [INFO]   - MSFT (SMART): 50.0 shares @ avg cost 380.25
2025-10-19 10:30:16 [INFO]   - GOOGL (SMART): 25.0 shares @ avg cost 142.80

================================================================================
Processing 3 position(s)...
================================================================================

2025-10-19 10:30:17 [INFO] Processing AAPL: 100.0 shares
2025-10-19 10:30:17 [INFO]   Submitting SELL market order for 100.0 shares...
2025-10-19 10:30:17 [INFO]   ✓ Order submitted (Order ID: 12345)
2025-10-19 10:30:18 [INFO] Processing MSFT: 50.0 shares
2025-10-19 10:30:18 [INFO]   Submitting SELL market order for 50.0 shares...
2025-10-19 10:30:18 [INFO]   ✓ Order submitted (Order ID: 12346)
2025-10-19 10:30:19 [INFO] Processing GOOGL: 25.0 shares
2025-10-19 10:30:19 [INFO]   Submitting SELL market order for 25.0 shares...
2025-10-19 10:30:19 [INFO]   ✓ Order submitted (Order ID: 12347)

================================================================================
Waiting for order confirmations...
================================================================================

2025-10-19 10:30:25 [INFO] Checking order status... (5s)
2025-10-19 10:30:25 [INFO]   AAPL: Filled (100.0/100.0 filled)
2025-10-19 10:30:25 [INFO]   MSFT: Filled (50.0/50.0 filled)
2025-10-19 10:30:25 [INFO]   GOOGL: Filled (25.0/25.0 filled)

================================================================================
✓ Order monitoring complete
================================================================================

2025-10-19 10:30:45 [INFO] Fetching final positions...
2025-10-19 10:30:45 [INFO] ✓ Account cleared - no positions remaining
2025-10-19 10:30:45 [INFO] Disconnected from IB

✓ Script completed successfully
```

## Dry Run Example

```bash
$ python clear_ib_positions.py --dry-run

================================================================================
IB POSITION CLEARER
================================================================================

⚠ DRY RUN MODE - No orders will be submitted

2025-10-19 10:35:00 [INFO] Connecting to IB at localhost:7497 with client_id=1...
2025-10-19 10:35:01 [INFO] ✓ Connected to IB

2025-10-19 10:35:01 [INFO] Fetching current positions...
2025-10-19 10:35:01 [INFO] Found 3 position(s) in IB account:
2025-10-19 10:35:01 [INFO]   - AAPL (SMART): 100.0 shares @ avg cost 175.50
2025-10-19 10:35:01 [INFO]   - MSFT (SMART): 50.0 shares @ avg cost 380.25
2025-10-19 10:35:01 [INFO]   - GOOGL (SMART): 25.0 shares @ avg cost 142.80

================================================================================
Processing 3 position(s)...
================================================================================

2025-10-19 10:35:01 [INFO] Processing AAPL: 100.0 shares
2025-10-19 10:35:01 [INFO]   [DRY RUN] Would submit SELL market order for 100.0 shares
2025-10-19 10:35:01 [INFO] Processing MSFT: 50.0 shares
2025-10-19 10:35:01 [INFO]   [DRY RUN] Would submit SELL market order for 50.0 shares
2025-10-19 10:35:01 [INFO] Processing GOOGL: 25.0 shares
2025-10-19 10:35:01 [INFO]   [DRY RUN] Would submit SELL market order for 25.0 shares

================================================================================
DRY RUN COMPLETE - No orders were actually submitted
================================================================================

2025-10-19 10:35:01 [INFO] Disconnected from IB

✓ Script completed successfully
```

## Troubleshooting

### Connection Failed

**Error**: `Error connecting: [Errno 61] Connection refused`

**Solution**:
- Ensure IB Gateway or TWS is running
- Verify API connections are enabled: File → Global Configuration → API → Settings → "Enable ActiveX and Socket Clients"
- Check that the port matches: 7497 for paper trading, 7496 for live trading
- Ensure client ID is not already in use by another connection

### No Positions Found

**Message**: `No positions found in IB account`

**Solution**:
- This is normal if your account has no positions
- Verify you're connected to the correct account in IB Gateway
- Check the account dropdown in IB Gateway/TWS

### Order Submission Failed

**Error**: `Failed to submit order for AAPL: ...`

**Solution**:
- Contract may not be tradeable in paper trading mode
- Use dry-run mode first to identify problematic symbols
- Check IB TWS for contract details and tradability
- Verify you have sufficient permissions in paper trading account

### Positions Still Remaining

**Warning**: `⚠ 3 position(s) still remaining`

**Solution**:
- Orders may still be pending - wait a few more seconds
- Check IB TWS to see order status manually
- Run the script again if orders were cancelled
- In paper trading, orders sometimes take time to fill

## Port Numbers

- **7497**: IB Gateway paper trading (default)
- **7496**: IB Gateway live trading
- **7497**: TWS paper trading
- **7496**: TWS live trading

## Safety Features

1. **Dry Run Mode**: Test without submitting real orders
2. **Logging**: All actions logged with timestamps
3. **Error Handling**: Continues processing even if individual orders fail
4. **Order Monitoring**: Verifies order status after submission
5. **Final Verification**: Confirms positions are cleared

## Important Notes

⚠️ **This script submits MARKET orders** - execution price is not guaranteed

⚠️ **Paper trading recommended** - Test thoroughly before considering live use

⚠️ **No rollback** - Once orders are submitted, they cannot be automatically cancelled

⚠️ **Settlement time** - Orders may take a few seconds to fill in paper trading

⚠️ **Client ID conflicts** - Each IB connection needs a unique client ID

## Quick Start

1. **Start IB Gateway** (paper trading mode)
2. **Enable API** in settings
3. **Run dry-run** to test:
   ```bash
   python clear_ib_positions.py --dry-run
   ```
4. **Clear positions** for real:
   ```bash
   python clear_ib_positions.py
   ```

## Dependencies

```bash
pip install ib_insync
```

That's it! No other dependencies needed.
