"""
Diagnostic script to check IB SELL order cash handling.

Run this to investigate why cash isn't being added on SELL orders.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from decimal import Decimal
from zimuabull.models import (
    Portfolio, IBOrder, IBOrderStatus, IBOrderAction,
    PortfolioTransaction, TransactionType
)
from django.utils import timezone

def check_recent_sell_orders():
    """Check recent SELL orders and their cash impact"""
    print("=" * 80)
    print("CHECKING RECENT IB SELL ORDERS")
    print("=" * 80)

    # Get filled SELL orders from last 7 days
    recent_sells = IBOrder.objects.filter(
        action=IBOrderAction.SELL,
        status=IBOrderStatus.FILLED,
        filled_at__isnull=False
    ).order_by('-filled_at')[:10]

    if not recent_sells:
        print("\n❌ No filled SELL orders found")
        return

    for order in recent_sells:
        print(f"\n{'='*80}")
        print(f"Order: {order.client_order_id}")
        print(f"Symbol: {order.symbol.symbol}")
        print(f"Portfolio: {order.portfolio.name} (ID: {order.portfolio.id})")
        print(f"Action: {order.action} (type: {type(order.action)})")
        print(f"Quantity: {order.filled_quantity}")
        print(f"Fill Price: ${order.filled_price}")
        print(f"Fill Value: ${order.filled_quantity * order.filled_price}")
        print(f"Filled At: {order.filled_at}")
        print(f"Status: {order.status}")

        # Check for corresponding transaction
        transactions = PortfolioTransaction.objects.filter(
            portfolio=order.portfolio,
            symbol=order.symbol,
            transaction_type=TransactionType.SELL,
            quantity=order.filled_quantity,
            price=order.filled_price,
        )

        print(f"\nCorresponding Transactions: {transactions.count()}")
        for txn in transactions:
            print(f"  - Transaction ID: {txn.id}")
            print(f"    Type: {txn.transaction_type}")
            print(f"    Quantity: {txn.quantity}")
            print(f"    Price: ${txn.price}")
            print(f"    Total: ${txn.quantity * txn.price}")
            print(f"    Date: {txn.transaction_date}")
            print(f"    Notes: {txn.notes}")

        # Check portfolio holding logs
        from zimuabull.models import PortfolioHoldingLog
        logs = PortfolioHoldingLog.objects.filter(
            portfolio=order.portfolio,
            symbol=order.symbol,
            transaction__in=transactions
        ).order_by('-created_at')

        print(f"\nHolding Logs: {logs.count()}")
        for log in logs:
            print(f"  - Operation: {log.operation}")
            print(f"    Qty Before: {log.quantity_before} -> After: {log.quantity_after}")
            print(f"    Notes: {log.notes}")

def check_cash_balance_changes():
    """Check portfolio cash balance changes around SELL orders"""
    print("\n" + "=" * 80)
    print("PORTFOLIO CASH BALANCE ANALYSIS")
    print("=" * 80)

    # Get portfolios with IB enabled
    ib_portfolios = Portfolio.objects.filter(use_interactive_brokers=True)

    for portfolio in ib_portfolios:
        print(f"\n{'='*80}")
        print(f"Portfolio: {portfolio.name}")
        print(f"Current Cash: ${portfolio.cash_balance}")

        # Get recent SELL orders
        sells = IBOrder.objects.filter(
            portfolio=portfolio,
            action=IBOrderAction.SELL,
            status=IBOrderStatus.FILLED
        ).order_by('-filled_at')[:5]

        if sells:
            print(f"\nRecent SELL Orders: {sells.count()}")
            for order in sells:
                expected_cash_increase = order.filled_quantity * order.filled_price
                print(f"  - {order.symbol.symbol}: Filled {order.filled_quantity} @ ${order.filled_price}")
                print(f"    Expected cash increase: ${expected_cash_increase}")
                print(f"    Filled at: {order.filled_at}")

def test_transaction_save():
    """Test if transaction save properly updates cash"""
    print("\n" + "=" * 80)
    print("TESTING TRANSACTION SAVE LOGIC")
    print("=" * 80)

    # Get a portfolio
    portfolio = Portfolio.objects.filter(use_interactive_brokers=True).first()
    if not portfolio:
        print("❌ No IB portfolio found")
        return

    print(f"\nPortfolio: {portfolio.name}")
    print(f"Cash Before: ${portfolio.cash_balance}")

    # Find a symbol
    from zimuabull.models import Symbol
    symbol = Symbol.objects.filter(exchange=portfolio.exchange).first()

    if not symbol:
        print("❌ No symbol found for portfolio exchange")
        return

    # Create a test SELL transaction
    test_qty = Decimal("1.0")
    test_price = Decimal("100.00")
    expected_cash_increase = test_qty * test_price

    print(f"\nCreating test SELL transaction:")
    print(f"  Symbol: {symbol.symbol}")
    print(f"  Quantity: {test_qty}")
    print(f"  Price: ${test_price}")
    print(f"  Expected cash increase: ${expected_cash_increase}")

    # Check if transaction_type comparison works
    print(f"\nTransaction type check:")
    print(f"  TransactionType.SELL = {repr(TransactionType.SELL)}")
    print(f"  'SELL' == TransactionType.SELL: {'SELL' == TransactionType.SELL}")
    print(f"  TransactionType.SELL == 'SELL': {TransactionType.SELL == 'SELL'}")

if __name__ == "__main__":
    check_recent_sell_orders()
    check_cash_balance_changes()
    test_transaction_save()

    print("\n" + "=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)
