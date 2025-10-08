# Portfolio Transaction System Guide

The portfolio system has been upgraded to a transaction-based model where holdings are automatically calculated from buy/sell transactions.

## Key Changes

### 1. Cash Balance System
- Every portfolio starts with **$10,000 cash** (configurable)
- Cash is automatically updated on every transaction
- Cannot spend more than available cash

### 2. Transaction-Based Holdings
- Holdings are NO LONGER created directly
- Instead, create **transactions** (BUY/SELL)
- Holdings are automatically calculated from transaction history

### 3. Automatic Calculations
- **Average cost basis**: Calculated when buying multiple times
- **Holdings**: Updated automatically on BUY/SELL
- **Cash balance**: Deducted on BUY, added on SELL
- **Gains**: Realized + unrealized tracked separately

## API Usage

### Create a Transaction (BUY)

```bash
POST /api/transactions/
Content-Type: application/json

{
  "portfolio": 1,
  "symbol_ticker": "AAPL",
  "exchange_code": "NASDAQ",
  "transaction_type": "BUY",
  "quantity": 10,
  "price": 175.50,
  "transaction_date": "2025-10-08",
  "notes": "First purchase"
}
```

**What happens:**
- Cash: $10,000 - $1,755 = $8,245
- Holding created: 10 shares AAPL @ $175.50 average cost

### Create a Transaction (SELL)

```bash
POST /api/transactions/
Content-Type: application/json

{
  "portfolio": 1,
  "symbol_ticker": "AAPL",
  "exchange_code": "NASDAQ",
  "transaction_type": "SELL",
  "quantity": 5,
  "price": 180.00,
  "transaction_date": "2025-10-09",
  "notes": "Taking profits"
}
```

**What happens:**
- Cash: $8,245 + $900 = $9,145
- Holding updated: 5 shares AAPL @ $175.50 average cost (unchanged)
- Realized gain: $22.50 (5 × ($180 - $175.50))

### View Holdings (Read-Only)

```bash
# List all holdings
GET /api/holdings/

# Filter by portfolio
GET /api/holdings/?portfolio=1

# Get specific holding
GET /api/holdings/123/
```

### View Transactions

```bash
# List all transactions
GET /api/transactions/

# Filter by portfolio
GET /api/transactions/?portfolio=1
```

### View Portfolio with Cash Balance

```bash
GET /api/portfolios/1/
```

Response includes:
```json
{
  "id": 1,
  "name": "My Portfolio",
  "cash_balance": 9145.00,
  "holdings_value": 877.50,  // 5 shares × current price
  "total_value": 10022.50,   // cash + holdings
  "holdings": [...]
}
```

## Validations

### Cannot Overspend

```bash
POST /api/transactions/
{
  "transaction_type": "BUY",
  "quantity": 100,
  "price": 200.00  // $20,000 total
}
```

Response (400 Bad Request):
```json
{
  "non_field_errors": [
    "Insufficient funds. Need $20000.00 but only have $9145.00 in cash"
  ]
}
```

### Cannot Oversell

```bash
POST /api/transactions/
{
  "transaction_type": "SELL",
  "quantity": 20  // Only own 5 shares
}
```

Response (400 Bad Request):
```json
{
  "quantity": [
    "Cannot sell 20 shares. You only own 5 shares"
  ]
}
```

### Cannot Sell What You Don't Own

```bash
POST /api/transactions/
{
  "symbol_ticker": "MSFT",  // Don't own any MSFT
  "transaction_type": "SELL"
}
```

Response (400 Bad Request):
```json
{
  "non_field_errors": [
    "You don't own any shares of MSFT to sell"
  ]
}
```

## Migration Instructions

### Run Migrations

```bash
python manage.py migrate
```

This will:
1. Add `cash_balance` field to Portfolio
2. Create `PortfolioTransaction` table
3. Update `PortfolioHolding` structure
4. **Set all existing portfolios to $10,000 cash**

### Existing Holdings

If you have existing holdings created the old way:
1. They will continue to work (backward compatible)
2. But you should migrate to transactions for consistency
3. Old `purchase_price`, `purchase_date` fields removed
4. New `average_cost`, `first_purchase_date` fields added

### Data Migration Script

If you need to convert old holdings to transactions:

```python
# Example migration script
from zimuabull.models import PortfolioHolding, PortfolioTransaction
from datetime import date

# This is just an example - adjust as needed
for holding in PortfolioHolding.objects.filter(status='ACTIVE'):
    # Create a BUY transaction to represent the existing holding
    # Note: This won't work as-is since old fields are removed
    # You'd need to have backed up the data first
    pass
```

## Future Features (Already Supported)

The transaction model supports OPTIONS trading:

```python
transaction_type choices:
- BUY: Buy shares
- SELL: Sell shares
- CALL: Buy call option (future)
- PUT: Buy put option (future)

# For options:
strike_price: Option strike price
expiration_date: Option expiration date
```

## Benefits of Transaction System

1. **Immutable audit trail** - All buys/sells permanently recorded
2. **Accurate cost basis** - Automatic average cost calculation
3. **Cash management** - Cannot overspend
4. **Realized vs unrealized** - Separate gain tracking
5. **Partial sales** - Handled automatically
6. **Options ready** - Structure supports future options trading

## Example Workflow

```bash
# 1. Create portfolio with $10k cash
POST /api/portfolios/
{
  "name": "My Trading Portfolio",
  "country": "United States",
  "currency": "USD"
}
# Result: portfolio with $10,000 cash_balance

# 2. Buy 10 AAPL @ $175
POST /api/transactions/
{
  "portfolio": 1,
  "symbol_ticker": "AAPL",
  "exchange_code": "NASDAQ",
  "transaction_type": "BUY",
  "quantity": 10,
  "price": 175.00,
  "transaction_date": "2025-10-08"
}
# Result: Cash $8,250, Holding: 10 AAPL @ $175

# 3. Buy 5 more AAPL @ $180
POST /api/transactions/
{
  "portfolio": 1,
  "symbol_ticker": "AAPL",
  "exchange_code": "NASDAQ",
  "transaction_type": "BUY",
  "quantity": 5,
  "price": 180.00,
  "transaction_date": "2025-10-09"
}
# Result: Cash $7,350, Holding: 15 AAPL @ $176.67 average

# 4. Sell 8 AAPL @ $185
POST /api/transactions/
{
  "portfolio": 1,
  "symbol_ticker": "AAPL",
  "exchange_code": "NASDAQ",
  "transaction_type": "SELL",
  "quantity": 8,
  "price": 185.00,
  "transaction_date": "2025-10-10"
}
# Result: Cash $8,830, Holding: 7 AAPL @ $176.67 average
# Realized gain: $66.64 (8 × ($185 - $176.67))

# 5. View portfolio
GET /api/portfolios/1/
# Shows:
# - cash_balance: $8,830
# - holdings_value: 7 × current_price
# - total_value: cash + holdings
# - total_gain_loss: realized + unrealized gains
```

## Troubleshooting

### "Field 'purchase_price' not found"
- Old serializers still reference removed fields
- Already fixed in the codebase
- Holdings now use `average_cost` instead of `purchase_price`

### "Cannot create holding"
- Don't create holdings directly anymore
- Use transactions instead: `POST /api/transactions/`

### "Cash balance is 0"
- Run migrations to set initial $10,000 cash
- Migration automatically sets existing portfolios to $10k

## Summary

✅ **Use `/api/transactions/`** to buy/sell stocks
✅ **Use `/api/holdings/`** to view current positions (read-only)
✅ **Cash is managed automatically**
✅ **Average cost is calculated automatically**
✅ **Cannot overspend or oversell**
✅ **All portfolios start with $10,000 cash**
