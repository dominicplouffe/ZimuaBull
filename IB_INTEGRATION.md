# Interactive Brokers Integration

This document describes the Interactive Brokers (IB) integration for automated day trading in ZimuaBull.

## Overview

The ZimuaBull day trading system now supports **live trading via Interactive Brokers** using the `ib_insync` library. This allows portfolios to execute real market orders through IB Gateway or Trader Workstation (TWS).

## Key Features

- **Dual Mode Operation**: Each portfolio can operate in either simulation mode or live IB mode
- **Async Order Execution**: Orders are submitted to IB and monitored in the background
- **Order State Tracking**: Full visibility into order lifecycle (pending → submitted → filled)
- **Commission Tracking**: Actual IB commissions are recorded
- **Multiple Portfolios**: Each portfolio can have its own IB configuration and client ID

## Architecture

### Order Flow (IB Mode)

1. **Morning Session** (9:15 AM ET):
   - `run_morning_trading_session` generates recommendations
   - `execute_recommendations()` submits BUY market orders to IB
   - Creates `IBOrder` records with status SUBMITTED
   - Creates `DayTradePosition` records with status PENDING

2. **Order Monitoring** (Every 30 seconds):
   - `monitor_ib_orders` task checks status of all active orders
   - When order fills:
     - Updates `IBOrder` with fill price and commission
     - Creates `PortfolioTransaction` with actual fill price
     - Updates `DayTradePosition` to OPEN status
     - Updates portfolio cash balance

3. **Position Monitoring** (Every 10 minutes):
   - `monitor_intraday_positions` checks if stop/target prices hit
   - When stop/target hit:
     - Submits SELL market order to IB
     - Updates position to CLOSING status

4. **Close Session** (3:55 PM ET):
   - `close_intraday_positions` submits SELL orders for all open positions
   - Order monitor handles the fills

### Order Flow (Simulation Mode)

Original behavior preserved:
- Orders execute immediately with simulated slippage
- Positions created with OPEN status instantly
- No async monitoring required

## Database Models

### IBOrder

Tracks IB orders and their status:

```python
class IBOrder(models.Model):
    portfolio = ForeignKey(Portfolio)
    day_trade_position = ForeignKey(DayTradePosition)
    symbol = ForeignKey(Symbol)

    # IB identifiers
    ib_order_id = IntegerField()  # IB's assigned order ID
    ib_perm_id = IntegerField()  # IB's permanent ID
    client_order_id = CharField(unique=True)  # Our tracking ID

    # Order details
    action = CharField()  # BUY/SELL
    order_type = CharField()  # MKT/LMT/STP
    quantity = DecimalField()

    # Status
    status = CharField()  # PENDING/SUBMITTED/FILLED/CANCELLED/REJECTED

    # Execution
    filled_price = DecimalField()
    filled_quantity = DecimalField()
    commission = DecimalField()
```

### DayTradePosition Status Updates

New statuses added:
- **PENDING**: BUY order submitted but not filled
- **OPEN**: Position active (filled)
- **CLOSING**: SELL order submitted but not filled
- **CLOSED**: Position exited (sell filled)
- **CANCELLED**: Order cancelled

## Portfolio Configuration

Add IB settings to your Portfolio model via Django admin or API:

### Required Fields

- `use_interactive_brokers` (Boolean): Enable IB integration
- `ib_host` (String): IB Gateway/TWS host (e.g., "127.0.0.1")
- `ib_port` (Integer): Port number
  - 4001: IB Gateway live
  - 4002: IB Gateway paper
  - 7497: TWS live
  - 7496: TWS paper
- `ib_client_id` (Integer): Unique client ID (1-999)
  - Each portfolio must have a different client ID

### Optional Fields

- `ib_account` (String): Account number (if you have multiple accounts)
- `ib_is_paper` (Boolean): Paper trading flag (default: True)

### Example Configuration

```python
portfolio.use_interactive_brokers = True
portfolio.ib_host = "127.0.0.1"
portfolio.ib_port = 4002  # Paper trading
portfolio.ib_client_id = 1
portfolio.ib_is_paper = True
portfolio.save()
```

## Setup Instructions

### 1. Install Requirements

```bash
pip install -r requirements.txt
```

This installs `ib_insync==0.9.86`.

### 2. Run Migrations

```bash
python manage.py migrate
```

This creates the `IBOrder` table.

### 3. Configure IB Gateway/TWS

#### Install IB Gateway
- Download from: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
- Or use TWS (Trader Workstation)

#### Enable API Access
1. Open IB Gateway/TWS
2. Go to **Configure** → **Settings** → **API** → **Settings**
3. Enable:
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Allow connections from localhost
4. Set Socket Port:
   - Live: 4001 (Gateway) or 7497 (TWS)
   - Paper: 4002 (Gateway) or 7496 (TWS)
5. Add **127.0.0.1** to Trusted IPs
6. Disable "Read-Only API" (to allow trading)

### 4. Test Connection

```bash
python manage.py test_ib_connection <portfolio_id>
```

This validates:
- IB Gateway/TWS is running
- API is enabled
- Connection settings are correct
- Authentication works

### 5. Start Celery Workers

```bash
# Start worker
celery -A core worker -l info -Q pidashtasks

# Start beat scheduler (in separate terminal)
celery -A core beat -l info
```

The beat scheduler will run:
- `ib_order_monitor`: Every 30 seconds (checks order status)
- `ib_order_cleanup`: Every 15 minutes (cancels stale orders)
- All existing day trading tasks

## Usage

### Enable IB for a Portfolio

```python
from zimuabull.models import Portfolio

portfolio = Portfolio.objects.get(id=1)
portfolio.use_interactive_brokers = True
portfolio.ib_host = "127.0.0.1"
portfolio.ib_port = 4002
portfolio.ib_client_id = 1
portfolio.save()
```

### Manual Testing

```python
from zimuabull.daytrading.ib_connector import IBConnector
from zimuabull.models import Portfolio

portfolio = Portfolio.objects.get(id=1)
connector = IBConnector(portfolio)
connector.connect()

# Test order submission
symbol = Symbol.objects.get(symbol="AAPL")
trade = connector.submit_market_order(
    symbol=symbol,
    action="BUY",
    quantity=1
)

print(f"Order ID: {trade.order.orderId}")
connector.disconnect()
```

### Monitor Orders

Check order status in Django admin:
- Navigate to **IB Orders**
- Filter by status, portfolio, or symbol
- View fill prices, commissions, and error messages

## Error Handling

### Connection Errors

**Symptom**: `IBConnectionError: Connection failed`

**Solutions**:
1. Ensure IB Gateway/TWS is running
2. Check API settings are enabled
3. Verify port number matches
4. Check firewall/network settings
5. Ensure client_id is unique

### Order Rejections

Orders can be rejected for:
- Insufficient buying power
- Symbol not found / invalid contract
- Market closed
- Permissions (e.g., shorting not allowed)

Check `IBOrder.error_message` field for details.

### Stale Orders

Orders pending for >10 minutes are automatically cancelled by `cancel_stale_ib_orders` task.

## Monitoring & Debugging

### Celery Logs

Monitor order execution in Celery worker logs:

```bash
celery -A core worker -l info -Q pidashtasks
```

Look for:
- `IB BUY order submitted`
- `Order FILLED`
- `Position opened`
- Connection errors

### Django Admin

- **IB Orders**: View all orders and their status
- **Day Trade Positions**: Check position status (PENDING/OPEN/CLOSING/CLOSED)
- **Portfolio Transactions**: Verify transactions created after fills

### Management Commands

```bash
# Test connection
python manage.py test_ib_connection 1

# Check portfolio health
python manage.py weekly_portfolio_review
```

## Safety Features

### Paper Trading First
- Always test with paper trading (`ib_is_paper=True`) first
- Use port 4002 (Gateway) or 7496 (TWS) for paper

### Order Validation
- Checks portfolio cash balance before submission
- Validates exchange matches portfolio
- Prevents duplicate positions
- Enforces fractional share settings

### Automatic Cleanup
- Stale orders (>10 min) automatically cancelled
- Positions auto-close at market close

### Read-Only Operations
- Order monitor only reads status (never modifies IB orders)
- All modifications go through tracked transactions

## Comparison: IB Mode vs Simulation

| Feature | Simulation Mode | IB Mode |
|---------|----------------|---------|
| Order Execution | Instant | Async (30s check) |
| Fill Price | Estimated + slippage | Actual market fill |
| Commissions | Estimated | Actual IB commissions |
| Cash Management | Immediate | After fill |
| Position Status | OPEN immediately | PENDING → OPEN |
| Errors | None | Real market rejections |
| Testing | Safe, always works | Requires IB Gateway |

## Troubleshooting

### Problem: Orders not filling

**Check**:
1. Is market open?
2. Is symbol valid?
3. Check `IBOrder.status_message` for IB errors
4. Review Celery logs for monitor task errors

### Problem: Duplicate orders

**Check**:
1. Is beat scheduler running only once?
2. Check for position with status PENDING already exists
3. Review morning session logs

### Problem: Connection timeout

**Check**:
1. IB Gateway running?
2. Correct port and client_id?
3. Client_id not in use by another connection?
4. Network/firewall blocking connection?

## Files Modified

### New Files
- `zimuabull/daytrading/ib_connector.py` - IB connection management
- `zimuabull/tasks/ib_order_monitor.py` - Order monitoring tasks
- `zimuabull/management/commands/test_ib_connection.py` - Testing tool
- `zimuabull/migrations/0030_*.py` - Database migration

### Modified Files
- `zimuabull/models.py` - Added IBOrder model, updated statuses
- `zimuabull/daytrading/trading_engine.py` - IB integration in order execution
- `zimuabull/admin.py` - IBOrder admin interface
- `core/settings.py` - Added ib_order_monitor to Celery beat
- `requirements.txt` - Added ib_insync

## Future Enhancements

Possible improvements:
- Limit orders (currently only market orders)
- Stop-limit orders
- Real-time market data streaming
- Options trading support
- Multi-leg strategies
- Position sizing based on IB buying power

## Support

For issues:
1. Check Celery logs
2. Check Django admin for order status
3. Run `test_ib_connection` command
4. Review IB Gateway/TWS logs
5. Consult IB API documentation: https://interactivebrokers.github.io/tws-api/

## References

- **ib_insync Documentation**: https://ib-insync.readthedocs.io/
- **IB API Guide**: https://interactivebrokers.github.io/tws-api/
- **IB Gateway Setup**: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
