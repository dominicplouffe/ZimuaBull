#!/usr/bin/env python
"""
Test holding logging functionality
"""
import os
import django
from decimal import Decimal
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from zimuabull.models import (
    Portfolio, Symbol, PortfolioTransaction,
    PortfolioHolding, PortfolioHoldingLog
)

def test_holding_operations():
    """Test BUY and SELL operations with logging"""

    print("\n" + "="*100)
    print("TESTING HOLDING OPERATIONS WITH LOGGING")
    print("="*100 + "\n")

    # Get or create a test portfolio
    from django.contrib.auth.models import User
    user = User.objects.first()
    if not user:
        print("ERROR: No users found. Please create a user first.")
        return

    # Get an exchange and symbol
    from zimuabull.models import Exchange
    exchange = Exchange.objects.first()
    if not exchange:
        print("ERROR: No exchanges found. Please create an exchange first.")
        return

    symbol = Symbol.objects.filter(exchange=exchange).first()
    if not symbol:
        print("ERROR: No symbols found. Please create a symbol first.")
        return

    # Create a test portfolio
    portfolio, created = Portfolio.objects.get_or_create(
        name="Test Logging Portfolio",
        user=user,
        exchange=exchange,
        defaults={'cash_balance': Decimal('10000.00')}
    )

    if created:
        print(f"✓ Created test portfolio: {portfolio.name}")
    else:
        print(f"✓ Using existing portfolio: {portfolio.name}")
        # Reset cash balance for testing
        portfolio.cash_balance = Decimal('10000.00')
        portfolio.save()

    print(f"  Initial cash: ${portfolio.cash_balance}")
    print(f"  Symbol: {symbol.symbol}")
    print()

    # Check initial holdings
    initial_holdings = portfolio.holdings.filter(status="ACTIVE")
    print(f"Initial active holdings: {initial_holdings.count()}")
    if initial_holdings.exists():
        for h in initial_holdings:
            print(f"  - {h.symbol.symbol}: {h.quantity} shares")
    print()

    # TEST 1: BUY transaction
    print("TEST 1: Creating BUY transaction")
    print("-" * 100)
    buy_qty = Decimal('10.5000')
    buy_price = Decimal('50.00')

    buy_txn = PortfolioTransaction.objects.create(
        portfolio=portfolio,
        symbol=symbol,
        transaction_type='BUY',
        quantity=buy_qty,
        price=buy_price,
        transaction_date=date.today()
    )

    print(f"✓ BUY transaction created: {buy_qty} shares @ ${buy_price}")
    portfolio.refresh_from_db()
    print(f"  Cash after BUY: ${portfolio.cash_balance}")

    # Check holding
    try:
        holding = PortfolioHolding.objects.get(
            portfolio=portfolio,
            symbol=symbol,
            status="ACTIVE"
        )
        print(f"✓ Holding exists: {holding.quantity} shares @ avg ${holding.average_cost}")
    except PortfolioHolding.DoesNotExist:
        print("✗ ERROR: Holding not created!")

    # Check log
    logs = PortfolioHoldingLog.objects.filter(transaction=buy_txn)
    print(f"✓ Logs created: {logs.count()}")
    for log in logs:
        print(f"  - {log.operation}: {log.notes}")
    print()

    # TEST 2: BUY more (update holding)
    print("TEST 2: Creating another BUY transaction (should UPDATE holding)")
    print("-" * 100)
    buy_qty2 = Decimal('5.0000')
    buy_price2 = Decimal('55.00')

    buy_txn2 = PortfolioTransaction.objects.create(
        portfolio=portfolio,
        symbol=symbol,
        transaction_type='BUY',
        quantity=buy_qty2,
        price=buy_price2,
        transaction_date=date.today()
    )

    print(f"✓ BUY transaction created: {buy_qty2} shares @ ${buy_price2}")
    portfolio.refresh_from_db()
    print(f"  Cash after BUY: ${portfolio.cash_balance}")

    # Check holding
    try:
        holding = PortfolioHolding.objects.get(
            portfolio=portfolio,
            symbol=symbol,
            status="ACTIVE"
        )
        print(f"✓ Holding updated: {holding.quantity} shares @ avg ${holding.average_cost}")
        expected_qty = buy_qty + buy_qty2
        print(f"  Expected: {expected_qty} shares")
        if holding.quantity == expected_qty:
            print(f"  ✓ Quantity is CORRECT")
        else:
            print(f"  ✗ Quantity is WRONG! Expected {expected_qty}, got {holding.quantity}")
    except PortfolioHolding.DoesNotExist:
        print("✗ ERROR: Holding not found!")

    # Check log
    logs = PortfolioHoldingLog.objects.filter(transaction=buy_txn2)
    print(f"✓ Logs created: {logs.count()}")
    for log in logs:
        print(f"  - {log.operation}: {log.notes}")
    print()

    # TEST 3: PARTIAL SELL
    print("TEST 3: Creating SELL transaction (partial sell)")
    print("-" * 100)
    sell_qty = Decimal('8.0000')
    sell_price = Decimal('60.00')

    sell_txn = PortfolioTransaction.objects.create(
        portfolio=portfolio,
        symbol=symbol,
        transaction_type='SELL',
        quantity=sell_qty,
        price=sell_price,
        transaction_date=date.today()
    )

    print(f"✓ SELL transaction created: {sell_qty} shares @ ${sell_price}")
    portfolio.refresh_from_db()
    print(f"  Cash after SELL: ${portfolio.cash_balance}")

    # Check holding
    try:
        holding = PortfolioHolding.objects.get(
            portfolio=portfolio,
            symbol=symbol,
            status="ACTIVE"
        )
        print(f"✓ Holding still exists: {holding.quantity} shares @ avg ${holding.average_cost}")
        expected_qty = buy_qty + buy_qty2 - sell_qty
        print(f"  Expected: {expected_qty} shares")
        if holding.quantity == expected_qty:
            print(f"  ✓ Quantity is CORRECT")
        else:
            print(f"  ✗ Quantity is WRONG! Expected {expected_qty}, got {holding.quantity}")
    except PortfolioHolding.DoesNotExist:
        print("✗ ERROR: Holding was deleted (should still exist for partial sell)!")

    # Check log
    logs = PortfolioHoldingLog.objects.filter(transaction=sell_txn)
    print(f"✓ Logs created: {logs.count()}")
    for log in logs:
        print(f"  - {log.operation}: {log.notes}")
    print()

    # TEST 4: FULL SELL
    print("TEST 4: Creating SELL transaction (full sell - should DELETE holding)")
    print("-" * 100)

    # Get current holding quantity
    try:
        holding = PortfolioHolding.objects.get(
            portfolio=portfolio,
            symbol=symbol,
            status="ACTIVE"
        )
        remaining_qty = holding.quantity
        print(f"Current holding: {remaining_qty} shares")
    except PortfolioHolding.DoesNotExist:
        print("✗ ERROR: No holding found to sell!")
        return

    sell_price2 = Decimal('65.00')

    sell_txn2 = PortfolioTransaction.objects.create(
        portfolio=portfolio,
        symbol=symbol,
        transaction_type='SELL',
        quantity=remaining_qty,
        price=sell_price2,
        transaction_date=date.today()
    )

    print(f"✓ SELL transaction created: {remaining_qty} shares @ ${sell_price2}")
    portfolio.refresh_from_db()
    print(f"  Cash after SELL: ${portfolio.cash_balance}")

    # Check holding - should NOT exist
    try:
        holding = PortfolioHolding.objects.get(
            portfolio=portfolio,
            symbol=symbol,
            status="ACTIVE"
        )
        print(f"✗ ERROR: Holding still exists with {holding.quantity} shares (should be deleted)!")
        print(f"  This is the BUG you're looking for!")
    except PortfolioHolding.DoesNotExist:
        print("✓ Holding correctly deleted (position fully closed)")

    # Check log
    logs = PortfolioHoldingLog.objects.filter(transaction=sell_txn2)
    print(f"✓ Logs created: {logs.count()}")
    for log in logs:
        print(f"  - {log.operation}: {log.notes}")
    print()

    # SUMMARY
    print("="*100)
    print("TEST SUMMARY")
    print("="*100)
    print(f"\nAll logs for portfolio {portfolio.id}:")
    all_logs = PortfolioHoldingLog.objects.filter(portfolio=portfolio).order_by('created_at')
    print(f"\n{'Operation':<12} {'Type':<6} {'Qty':<10} {'Before':<10} {'After':<10} {'Status':<10}")
    print("-" * 70)
    for log in all_logs:
        qty_before = f"{log.quantity_before:.4f}" if log.quantity_before else "N/A"
        qty_after = f"{log.quantity_after:.4f}" if log.quantity_after else "N/A"
        print(f"{log.operation:<12} {log.transaction_type:<6} {log.transaction_quantity:>9.4f} {qty_before:>9} {qty_after:>9} {log.holding_status:<10}")
    print("-" * 70)

    print(f"\nFinal portfolio state:")
    print(f"  Cash: ${portfolio.cash_balance}")
    active_holdings = portfolio.holdings.filter(status="ACTIVE")
    print(f"  Active holdings: {active_holdings.count()}")
    for h in active_holdings:
        print(f"    - {h.symbol.symbol}: {h.quantity} shares @ avg ${h.average_cost}")

    print("\n" + "="*100 + "\n")


if __name__ == '__main__':
    test_holding_operations()
