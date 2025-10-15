#!/usr/bin/env python
"""
View holding logs for debugging portfolio transactions
"""
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from zimuabull.models import Portfolio, PortfolioHoldingLog
import sys

def view_holding_logs(portfolio_id=None, symbol_symbol=None, operation=None, limit=50):
    """View holding logs with optional filters"""

    logs = PortfolioHoldingLog.objects.all()

    if portfolio_id:
        logs = logs.filter(portfolio_id=portfolio_id)
        try:
            portfolio = Portfolio.objects.get(id=portfolio_id)
            print(f"\n{'='*100}")
            print(f"HOLDING LOGS FOR: {portfolio.name} (ID: {portfolio_id})")
            print(f"{'='*100}\n")
        except Portfolio.DoesNotExist:
            print(f"Portfolio {portfolio_id} not found")
            return

    if symbol_symbol:
        logs = logs.filter(symbol__symbol=symbol_symbol)
        print(f"Filtering by symbol: {symbol_symbol}")

    if operation:
        logs = logs.filter(operation=operation)
        print(f"Filtering by operation: {operation}")

    logs = logs.order_by('-created_at')[:limit]

    if not logs.exists():
        print("No logs found with the specified filters")
        return

    print(f"\nTotal logs found: {logs.count()}\n")
    print(f"{'Timestamp':<20} {'Operation':<12} {'Symbol':<8} {'Type':<6} {'Txn Qty':<12} {'Before':<12} {'After':<12} {'Status':<10}")
    print(f"{'-'*120}")

    for log in logs:
        timestamp = log.created_at.strftime("%Y-%m-%d %H:%M:%S")
        qty_before = f"{log.quantity_before:.4f}" if log.quantity_before is not None else "N/A"
        qty_after = f"{log.quantity_after:.4f}" if log.quantity_after is not None else "N/A"

        print(f"{timestamp:<20} {log.operation:<12} {log.symbol.symbol:<8} {log.transaction_type:<6} {log.transaction_quantity:>11.4f} {qty_before:>11} {qty_after:>11} {log.holding_status:<10}")

        # Show notes if they contain important information
        if log.notes and ("ERROR" in log.notes or "DELETED" in log.notes):
            print(f"  └─ NOTE: {log.notes}")

    print(f"{'-'*120}\n")

    # Show summary by operation type
    print("\nSUMMARY BY OPERATION:")
    print(f"{'Operation':<15} {'Count':<10}")
    print(f"{'-'*30}")

    from django.db.models import Count
    summary = PortfolioHoldingLog.objects.values('operation').annotate(count=Count('id')).order_by('-count')

    if portfolio_id:
        summary = summary.filter(portfolio_id=portfolio_id)

    for item in summary:
        print(f"{item['operation']:<15} {item['count']:<10}")

    print(f"{'-'*30}\n")


if __name__ == '__main__':
    # Get portfolio ID from command line or default to 15
    portfolio_id = int(sys.argv[1]) if len(sys.argv) > 1 else 15

    # Optional filters
    symbol = sys.argv[2] if len(sys.argv) > 2 else None
    operation = sys.argv[3] if len(sys.argv) > 3 else None

    view_holding_logs(portfolio_id=portfolio_id, symbol_symbol=symbol, operation=operation)
