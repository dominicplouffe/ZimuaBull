#!/usr/bin/env python
"""
Diagnose portfolio holding issues by analyzing logs and current state
"""
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from zimuabull.models import (
    Portfolio, PortfolioHolding, PortfolioTransaction,
    PortfolioHoldingLog, Symbol
)
from django.db.models import Sum, Count
import sys

def diagnose_portfolio(portfolio_id):
    """Comprehensive diagnosis of portfolio holding issues"""

    try:
        portfolio = Portfolio.objects.get(id=portfolio_id)
    except Portfolio.DoesNotExist:
        print(f"Portfolio {portfolio_id} not found")
        return

    print(f"\n{'='*100}")
    print(f"PORTFOLIO DIAGNOSIS: {portfolio.name} (ID: {portfolio_id})")
    print(f"{'='*100}\n")

    # 1. Check for SELL_ERROR logs
    print("1. CHECKING FOR SELL ERRORS")
    print("-" * 100)
    sell_errors = PortfolioHoldingLog.objects.filter(
        portfolio=portfolio,
        operation='SELL_ERROR'
    )

    if sell_errors.exists():
        print(f"⚠️  FOUND {sell_errors.count()} SELL ERRORS:")
        for error in sell_errors:
            print(f"  - {error.created_at}: {error.symbol.symbol}")
            print(f"    Transaction: SELL {error.transaction_quantity} @ ${error.transaction_price}")
            print(f"    Note: {error.notes}")
            print()
    else:
        print("✓ No sell errors found")
    print()

    # 2. Check for holdings with zero or negative quantity
    print("2. CHECKING FOR INVALID HOLDINGS (zero or negative quantity)")
    print("-" * 100)
    invalid_holdings = PortfolioHolding.objects.filter(
        portfolio=portfolio,
        status='ACTIVE',
        quantity__lte=0
    )

    if invalid_holdings.exists():
        print(f"⚠️  FOUND {invalid_holdings.count()} INVALID HOLDINGS:")
        for holding in invalid_holdings:
            print(f"  - {holding.symbol.symbol}: {holding.quantity} shares (SHOULD BE DELETED)")

            # Find the SELL transaction that should have deleted it
            last_log = PortfolioHoldingLog.objects.filter(
                portfolio=portfolio,
                symbol=holding.symbol,
                operation__in=['UPDATE', 'DELETE']
            ).order_by('-created_at').first()

            if last_log:
                print(f"    Last operation: {last_log.operation} at {last_log.created_at}")
                print(f"    {last_log.notes}")
            print()
    else:
        print("✓ No invalid holdings found")
    print()

    # 3. Analyze holding operations by symbol
    print("3. HOLDINGS WITH SUSPICIOUS PATTERNS")
    print("-" * 100)

    # Get all symbols that have been traded
    traded_symbols = PortfolioHoldingLog.objects.filter(
        portfolio=portfolio
    ).values_list('symbol', flat=True).distinct()

    suspicious_found = False

    for symbol_id in traded_symbols:
        symbol = Symbol.objects.get(id=symbol_id)

        # Get all logs for this symbol
        logs = PortfolioHoldingLog.objects.filter(
            portfolio=portfolio,
            symbol=symbol
        ).order_by('created_at')

        # Calculate expected final quantity
        final_qty = Decimal('0')
        for log in logs:
            if log.operation == 'CREATE':
                final_qty = log.quantity_after
            elif log.operation == 'UPDATE':
                if log.transaction_type == 'BUY':
                    final_qty = log.quantity_after
                else:  # SELL
                    final_qty = log.quantity_after
            elif log.operation == 'DELETE':
                final_qty = Decimal('0')

        # Check if current holding matches expected
        try:
            current_holding = PortfolioHolding.objects.get(
                portfolio=portfolio,
                symbol=symbol,
                status='ACTIVE'
            )
            current_qty = current_holding.quantity

            if current_qty != final_qty:
                suspicious_found = True
                print(f"⚠️  MISMATCH: {symbol.symbol}")
                print(f"  Expected quantity: {final_qty}")
                print(f"  Actual quantity: {current_qty}")
                print(f"  Difference: {current_qty - final_qty}")
                print(f"  Total operations: {logs.count()}")
                print()

        except PortfolioHolding.DoesNotExist:
            if final_qty != Decimal('0'):
                suspicious_found = True
                print(f"⚠️  MISSING HOLDING: {symbol.symbol}")
                print(f"  Expected quantity: {final_qty}")
                print(f"  Actual: No holding found")
                print(f"  Last operation: {logs.last().operation}")
                print()

    if not suspicious_found:
        print("✓ No suspicious patterns found")
    print()

    # 4. Compare transactions with logs
    print("4. TRANSACTION vs LOG CONSISTENCY CHECK")
    print("-" * 100)

    transactions = PortfolioTransaction.objects.filter(
        portfolio=portfolio,
        transaction_type__in=['BUY', 'SELL']
    )

    txns_without_logs = []
    for txn in transactions:
        log_exists = PortfolioHoldingLog.objects.filter(transaction=txn).exists()
        if not log_exists:
            txns_without_logs.append(txn)

    if txns_without_logs:
        print(f"⚠️  FOUND {len(txns_without_logs)} TRANSACTIONS WITHOUT LOGS:")
        print("These transactions were created BEFORE logging was implemented")
        for txn in txns_without_logs[:10]:  # Show first 10
            print(f"  - {txn.transaction_date}: {txn.transaction_type} {txn.quantity} {txn.symbol.symbol}")
        if len(txns_without_logs) > 10:
            print(f"  ... and {len(txns_without_logs) - 10} more")
        print()
    else:
        print("✓ All transactions have corresponding logs")
    print()

    # 5. Summary statistics
    print("5. SUMMARY STATISTICS")
    print("-" * 100)

    total_logs = PortfolioHoldingLog.objects.filter(portfolio=portfolio).count()
    creates = PortfolioHoldingLog.objects.filter(portfolio=portfolio, operation='CREATE').count()
    updates = PortfolioHoldingLog.objects.filter(portfolio=portfolio, operation='UPDATE').count()
    deletes = PortfolioHoldingLog.objects.filter(portfolio=portfolio, operation='DELETE').count()
    errors = PortfolioHoldingLog.objects.filter(portfolio=portfolio, operation='SELL_ERROR').count()

    print(f"Total logs: {total_logs}")
    print(f"  - CREATE operations: {creates}")
    print(f"  - UPDATE operations: {updates}")
    print(f"  - DELETE operations: {deletes}")
    print(f"  - SELL_ERROR operations: {errors}")
    print()

    active_holdings = PortfolioHolding.objects.filter(
        portfolio=portfolio,
        status='ACTIVE'
    ).count()

    total_txns = PortfolioTransaction.objects.filter(
        portfolio=portfolio
    ).count()

    print(f"Current active holdings: {active_holdings}")
    print(f"Total transactions: {total_txns}")
    print()

    # 6. Recommendations
    print("6. RECOMMENDATIONS")
    print("-" * 100)

    if sell_errors.exists():
        print("• Investigate SELL_ERROR operations - these indicate attempts to sell non-existent holdings")

    if invalid_holdings.exists():
        print("• Clean up invalid holdings with zero/negative quantity")
        print("  You can delete these manually or run a cleanup script")

    if suspicious_found:
        print("• Review holdings with quantity mismatches")
        print("  The logs show what SHOULD be, vs what IS in the database")

    if not sell_errors.exists() and not invalid_holdings.exists() and not suspicious_found:
        print("✓ No issues detected! Portfolio holdings appear to be in good state.")

    print()
    print("To view detailed logs, run:")
    print(f"  .venv/bin/python view_holding_logs.py {portfolio_id}")
    print()
    print("="*100 + "\n")


if __name__ == '__main__':
    portfolio_id = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    diagnose_portfolio(portfolio_id)
