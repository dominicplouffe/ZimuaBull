# Cash Management Guide

Complete guide for managing portfolio cash including initial balance, deposits, and withdrawals.

## Features

✅ **Custom Initial Balance** - Set starting cash when creating portfolio
✅ **Deposit Cash** - Add money to portfolio anytime
✅ **Withdraw Cash** - Remove money from portfolio
✅ **Transaction History** - All cash movements tracked
✅ **Validation** - Cannot withdraw more than available

## Creating a Portfolio with Initial Balance

### Default ($10,000)

```bash
POST /api/portfolios/
{
  "name": "My Trading Portfolio",
  "description": "Main trading account",
  "country": "United States",
  "currency": "USD"
}
```

**Result:** Portfolio created with $10,000 cash

### Custom Initial Balance

```bash
POST /api/portfolios/
{
  "name": "My Trading Portfolio",
  "description": "Main trading account",
  "country": "United States",
  "currency": "USD",
  "initial_balance": 50000.00
}
```

**Result:** Portfolio created with $50,000 cash

**What happens:**
1. Portfolio created with specified cash_balance
2. Automatic DEPOSIT transaction created to track initial balance
3. Transaction shows in history as "Initial deposit of $50,000"

## Depositing Cash

Add money to your portfolio at any time:

```bash
POST /api/transactions/
{
  "portfolio": 1,
  "transaction_type": "DEPOSIT",
  "amount": 5000.00,
  "transaction_date": "2025-10-08",
  "notes": "Monthly contribution"
}
```

**What happens:**
- Cash balance increases by $5,000
- Transaction recorded in history
- No symbol/quantity/price required

**Example:**
```
Before: $10,000 cash
Deposit: $5,000
After:  $15,000 cash
```

## Withdrawing Cash

Remove money from your portfolio:

```bash
POST /api/transactions/
{
  "portfolio": 1,
  "transaction_type": "WITHDRAWAL",
  "amount": 2000.00,
  "transaction_date": "2025-10-08",
  "notes": "Living expenses"
}
```

**What happens:**
- Cash balance decreases by $2,000
- Transaction recorded in history
- Validated against available cash

**Example:**
```
Before: $15,000 cash
Withdraw: $2,000
After:  $13,000 cash
```

### Validation - Cannot Overdraw

```bash
POST /api/transactions/
{
  "portfolio": 1,
  "transaction_type": "WITHDRAWAL",
  "amount": 20000.00  // More than available
}
```

**Response (400 Bad Request):**
```json
{
  "amount": [
    "Insufficient funds. Cannot withdraw $20000.00, only have $13000.00 in cash"
  ]
}
```

## Transaction Types Summary

### Stock Transactions (require symbol)
```bash
# BUY - Purchase shares
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

# SELL - Sell shares
POST /api/transactions/
{
  "portfolio": 1,
  "symbol_ticker": "AAPL",
  "exchange_code": "NASDAQ",
  "transaction_type": "SELL",
  "quantity": 5,
  "price": 180.00,
  "transaction_date": "2025-10-09"
}
```

### Cash Transactions (no symbol needed)
```bash
# DEPOSIT - Add cash
POST /api/transactions/
{
  "portfolio": 1,
  "transaction_type": "DEPOSIT",
  "amount": 5000.00,
  "transaction_date": "2025-10-08"
}

# WITHDRAWAL - Remove cash
POST /api/transactions/
{
  "portfolio": 1,
  "transaction_type": "WITHDRAWAL",
  "amount": 2000.00,
  "transaction_date": "2025-10-08"
}
```

## Viewing Portfolio Cash

```bash
GET /api/portfolios/1/
```

**Response:**
```json
{
  "id": 1,
  "name": "My Trading Portfolio",
  "cash_balance": 13000.00,
  "holdings_value": 5250.00,  // Current market value of stocks
  "total_value": 18250.00,    // cash + holdings
  "holdings_count": 3
}
```

## Transaction History

View all transactions including cash movements:

```bash
GET /api/transactions/?portfolio=1
```

**Response includes all types:**
```json
{
  "results": [
    {
      "id": 1,
      "transaction_type": "DEPOSIT",
      "amount": 10000.00,
      "total_amount": 10000.00,
      "symbol_ticker": null,
      "transaction_date": "2025-10-01",
      "notes": "Initial deposit of $10000.00"
    },
    {
      "id": 2,
      "transaction_type": "BUY",
      "symbol_ticker": "AAPL",
      "quantity": 10.0,
      "price": 175.00,
      "total_amount": 1750.00,
      "transaction_date": "2025-10-02"
    },
    {
      "id": 3,
      "transaction_type": "DEPOSIT",
      "amount": 5000.00,
      "total_amount": 5000.00,
      "symbol_ticker": null,
      "transaction_date": "2025-10-05",
      "notes": "Monthly contribution"
    },
    {
      "id": 4,
      "transaction_type": "WITHDRAWAL",
      "amount": 2000.00,
      "total_amount": 2000.00,
      "symbol_ticker": null,
      "transaction_date": "2025-10-08",
      "notes": "Living expenses"
    }
  ]
}
```

## Complete Workflow Example

```bash
# 1. Create portfolio with $25,000
POST /api/portfolios/
{
  "name": "Growth Portfolio",
  "country": "United States",
  "currency": "USD",
  "initial_balance": 25000.00
}
# Cash: $25,000

# 2. Buy 50 shares of AAPL @ $175
POST /api/transactions/
{
  "portfolio": 1,
  "symbol_ticker": "AAPL",
  "exchange_code": "NASDAQ",
  "transaction_type": "BUY",
  "quantity": 50,
  "price": 175.00,
  "transaction_date": "2025-10-08"
}
# Cash: $16,250 (spent $8,750)
# Holdings: 50 AAPL

# 3. Add monthly contribution
POST /api/transactions/
{
  "portfolio": 1,
  "transaction_type": "DEPOSIT",
  "amount": 3000.00,
  "transaction_date": "2025-11-01",
  "notes": "November contribution"
}
# Cash: $19,250
# Holdings: 50 AAPL

# 4. Buy 25 shares of MSFT @ $380
POST /api/transactions/
{
  "portfolio": 1,
  "symbol_ticker": "MSFT",
  "exchange_code": "NASDAQ",
  "transaction_type": "BUY",
  "quantity": 25,
  "price": 380.00,
  "transaction_date": "2025-11-02"
}
# Cash: $9,750 (spent $9,500)
# Holdings: 50 AAPL, 25 MSFT

# 5. Sell 20 AAPL @ $185
POST /api/transactions/
{
  "portfolio": 1,
  "symbol_ticker": "AAPL",
  "exchange_code": "NASDAQ",
  "transaction_type": "SELL",
  "quantity": 20,
  "price": 185.00,
  "transaction_date": "2025-11-05"
}
# Cash: $13,450 (received $3,700)
# Holdings: 30 AAPL, 25 MSFT

# 6. Withdraw for emergency
POST /api/transactions/
{
  "portfolio": 1,
  "transaction_type": "WITHDRAWAL",
  "amount": 5000.00,
  "transaction_date": "2025-11-10",
  "notes": "Emergency fund"
}
# Cash: $8,450
# Holdings: 30 AAPL, 25 MSFT
```

## Migration Required

Run this migration to add the new fields:

```bash
python manage.py makemigrations
python manage.py migrate
```

Changes:
- `PortfolioTransaction.symbol` now nullable (for cash transactions)
- `PortfolioTransaction.amount` field added
- `PortfolioTransaction.transaction_type` max_length increased to 15
- `TransactionType` enum updated with DEPOSIT and WITHDRAWAL

## Benefits

1. **Full audit trail** - Every cash movement recorded
2. **Flexible starting capital** - Not limited to $10k default
3. **Add funds anytime** - Deposit when you want
4. **Withdraw profits** - Take money out when needed
5. **Cannot overdraw** - Validated withdrawals
6. **Complete history** - Track all money in/out

## Summary

✅ **Create Portfolio:**
```python
POST /api/portfolios/
{
  "name": "My Portfolio",
  "initial_balance": 50000  # Optional, defaults to 10000
}
```

✅ **Deposit Cash:**
```python
POST /api/transactions/
{
  "portfolio": 1,
  "transaction_type": "DEPOSIT",
  "amount": 5000
}
```

✅ **Withdraw Cash:**
```python
POST /api/transactions/
{
  "portfolio": 1,
  "transaction_type": "WITHDRAWAL",
  "amount": 2000
}
```

✅ **View Balance:**
```python
GET /api/portfolios/1/
# Returns: cash_balance, holdings_value, total_value
```
