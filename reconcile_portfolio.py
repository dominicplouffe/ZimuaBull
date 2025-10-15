#!/usr/bin/env python
"""
Reconcile portfolio 15 transactions and calculate expected value
"""
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from zimuabull.models import Portfolio, PortfolioTransaction, PortfolioHolding
from django.db.models import Sum

def reconcile_portfolio(portfolio_id):
    """Reconcile all transactions for a portfolio"""

    try:
        portfolio = Portfolio.objects.get(id=portfolio_id)
    except Portfolio.DoesNotExist:
        print(f"Portfolio {portfolio_id} not found")
        return

    print(f"\n{'='*80}")
    print(f"PORTFOLIO RECONCILIATION: {portfolio.name} (ID: {portfolio_id})")
    print(f"{'='*80}\n")

    # Get all transactions ordered chronologically
    transactions = portfolio.transactions.all().order_by('transaction_date', 'created_at')

    print(f"Total transactions: {transactions.count()}\n")

    # Track cash and holdings manually
    cash_balance = Decimal('0')
    holdings = {}  # symbol_id -> {quantity, total_cost}

    print(f"{'Date':<12} {'Type':<12} {'Symbol':<8} {'Qty':<10} {'Price':<10} {'Amount':<12} {'Cash Balance':<15}")
    print(f"{'-'*100}")

    for txn in transactions:
        if txn.transaction_type == 'DEPOSIT':
            cash_balance += txn.amount
            print(f"{txn.transaction_date} {'DEPOSIT':<12} {'-':<8} {'-':<10} {'-':<10} ${txn.amount:>10.2f} ${cash_balance:>13.2f}")

        elif txn.transaction_type == 'WITHDRAWAL':
            cash_balance -= txn.amount
            print(f"{txn.transaction_date} {'WITHDRAWAL':<12} {'-':<8} {'-':<10} {'-':<10} ${-txn.amount:>10.2f} ${cash_balance:>13.2f}")

        elif txn.transaction_type == 'BUY':
            symbol_id = txn.symbol.id
            symbol_code = txn.symbol.symbol
            amount = txn.quantity * txn.price
            cash_balance -= amount

            if symbol_id not in holdings:
                holdings[symbol_id] = {
                    'symbol': txn.symbol,
                    'quantity': Decimal('0'),
                    'total_cost': Decimal('0')
                }

            holdings[symbol_id]['quantity'] += txn.quantity
            holdings[symbol_id]['total_cost'] += amount

            print(f"{txn.transaction_date} {'BUY':<12} {symbol_code:<8} {txn.quantity:>9.4f} ${txn.price:>8.2f} ${-amount:>10.2f} ${cash_balance:>13.2f}")

        elif txn.transaction_type == 'SELL':
            symbol_id = txn.symbol.id
            symbol_code = txn.symbol.symbol
            amount = txn.quantity * txn.price
            cash_balance += amount

            if symbol_id in holdings:
                # Calculate proportion of cost basis being sold
                if holdings[symbol_id]['quantity'] > 0:
                    cost_per_share = holdings[symbol_id]['total_cost'] / holdings[symbol_id]['quantity']
                    cost_sold = cost_per_share * txn.quantity

                    holdings[symbol_id]['quantity'] -= txn.quantity
                    holdings[symbol_id]['total_cost'] -= cost_sold

                    # Remove if fully sold
                    if holdings[symbol_id]['quantity'] <= 0:
                        del holdings[symbol_id]

            print(f"{txn.transaction_date} {'SELL':<12} {symbol_code:<8} {txn.quantity:>9.4f} ${txn.price:>8.2f} ${amount:>10.2f} ${cash_balance:>13.2f}")

    print(f"{'-'*100}\n")

    # Calculate current holdings value
    print(f"\nCURRENT HOLDINGS:")
    print(f"{'Symbol':<10} {'Quantity':<15} {'Avg Cost':<12} {'Last Close':<12} {'Cost Basis':<15} {'Market Value':<15} {'P/L':<15}")
    print(f"{'-'*110}")

    total_holdings_cost = Decimal('0')
    total_holdings_value = Decimal('0')

    for symbol_id, holding_data in holdings.items():
        symbol = holding_data['symbol']
        quantity = holding_data['quantity']
        total_cost = holding_data['total_cost']
        avg_cost = total_cost / quantity if quantity > 0 else Decimal('0')

        # Get current price
        current_price = Decimal(str(symbol.last_close))
        market_value = quantity * current_price
        pl = market_value - total_cost

        total_holdings_cost += total_cost
        total_holdings_value += market_value

        print(f"{symbol.symbol:<10} {quantity:>14.4f} ${avg_cost:>10.2f} ${current_price:>10.2f} ${total_cost:>13.2f} ${market_value:>13.2f} ${pl:>13.2f}")

    print(f"{'-'*110}")
    print(f"{'TOTAL':<10} {'':<15} {'':<12} {'':<12} ${total_holdings_cost:>13.2f} ${total_holdings_value:>13.2f} ${total_holdings_value - total_holdings_cost:>13.2f}")

    # Summary
    print(f"\n{'='*80}")
    print(f"RECONCILIATION SUMMARY")
    print(f"{'='*80}")
    print(f"Expected Cash Balance:        ${cash_balance:>15.2f}")
    print(f"Expected Holdings Value:      ${total_holdings_value:>15.2f}")
    print(f"Expected Total Portfolio:     ${cash_balance + total_holdings_value:>15.2f}")
    print(f"\nActual Portfolio Cash:        ${portfolio.cash_balance:>15.2f}")
    print(f"Actual Holdings Value:        ${Decimal(str(portfolio.total_invested())):>15.2f}")
    print(f"Actual Total Portfolio:       ${Decimal(str(portfolio.current_value())):>15.2f}")
    print(f"\nCash Variance:                ${portfolio.cash_balance - cash_balance:>15.2f}")
    print(f"Holdings Variance:            ${Decimal(str(portfolio.total_invested())) - total_holdings_value:>15.2f}")
    print(f"Total Variance:               ${Decimal(str(portfolio.current_value())) - (cash_balance + total_holdings_value):>15.2f}")
    print(f"{'='*80}\n")

    # Compare with database holdings
    print(f"\nDATABASE HOLDINGS (Active):")
    db_holdings = portfolio.holdings.filter(status='ACTIVE')
    if db_holdings.exists():
        print(f"{'Symbol':<10} {'Quantity':<15} {'Avg Cost':<12} {'Cost Basis':<15}")
        print(f"{'-'*60}")
        for holding in db_holdings:
            print(f"{holding.symbol.symbol:<10} {holding.quantity:>14.4f} ${holding.average_cost:>10.2f} ${holding.cost_basis():>13.2f}")
    else:
        print("No active holdings in database")

    print(f"\n{'='*80}\n")

if __name__ == '__main__':
    reconcile_portfolio(15)
