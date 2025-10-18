"""
Check for cash balance discrepancies in portfolios.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from decimal import Decimal
from zimuabull.models import Portfolio, PortfolioTransaction, TransactionType

def check_portfolio_cash_accuracy(portfolio_id=15):
    """Check if portfolio cash balance matches transaction history"""
    portfolio = Portfolio.objects.get(id=portfolio_id)

    print(f"Portfolio: {portfolio.name}")
    print(f"Current Cash Balance: ${portfolio.cash_balance}")
    print(f"\n{'='*80}\n")

    # Calculate what cash should be based on all transactions
    transactions = PortfolioTransaction.objects.filter(
        portfolio=portfolio
    ).order_by('transaction_date', 'created_at')

    calculated_cash = Decimal("0")

    print("Transaction History (most recent 20):")
    print(f"{'Date':<12} {'Type':<10} {'Symbol':<8} {'Qty':<8} {'Price':<10} {'Cash Impact':<15} {'Running Cash':<15}")
    print("-" * 100)

    # Get initial deposits
    for txn in transactions:
        if txn.transaction_type == TransactionType.DEPOSIT:
            calculated_cash += txn.amount
        elif txn.transaction_type == TransactionType.WITHDRAWAL:
            calculated_cash -= txn.amount
        elif txn.transaction_type == TransactionType.BUY:
            calculated_cash -= (txn.quantity * txn.price)
        elif txn.transaction_type == TransactionType.SELL:
            calculated_cash += (txn.quantity * txn.price)

    # Show recent transactions
    recent = list(transactions.order_by('-created_at')[:20])
    recent.reverse()

    for txn in recent:
        symbol_str = txn.symbol.symbol if txn.symbol else "N/A"
        qty_str = f"{txn.quantity}" if txn.quantity else "0"
        price_str = f"${txn.price}" if txn.price else "$0"

        if txn.transaction_type == TransactionType.DEPOSIT:
            impact = f"+${txn.amount}"
        elif txn.transaction_type == TransactionType.WITHDRAWAL:
            impact = f"-${txn.amount}"
        elif txn.transaction_type == TransactionType.BUY:
            impact = f"-${txn.quantity * txn.price}"
        elif txn.transaction_type == TransactionType.SELL:
            impact = f"+${txn.quantity * txn.price}"
        else:
            impact = "$0"

        print(f"{txn.transaction_date} {txn.transaction_type:<10} {symbol_str:<8} {qty_str:<8} {price_str:<10} {impact:<15}")

    print("-" * 100)
    print(f"\nCalculated Cash (from all transactions): ${calculated_cash}")
    print(f"Portfolio Cash Balance:                   ${portfolio.cash_balance}")
    print(f"Discrepancy:                              ${portfolio.cash_balance - calculated_cash}")

    if abs(portfolio.cash_balance - calculated_cash) > Decimal("0.01"):
        print("\n⚠️  WARNING: Cash balance discrepancy detected!")

        # Check for missing transaction updates
        print("\nChecking for transactions that might not have updated cash...")

        # Look for SELL transactions specifically
        sell_txns = PortfolioTransaction.objects.filter(
            portfolio=portfolio,
            transaction_type=TransactionType.SELL
        ).order_by('-created_at')[:10]

        print(f"\nRecent SELL transactions: {sell_txns.count()}")
        for txn in sell_txns:
            print(f"  - {txn.symbol.symbol}: {txn.quantity} @ ${txn.price} = ${txn.quantity * txn.price}")
            print(f"    Date: {txn.transaction_date}, Created: {txn.created_at}")
            print(f"    Notes: {txn.notes}")
    else:
        print("\n✅ Cash balance is accurate!")

if __name__ == "__main__":
    check_portfolio_cash_accuracy()
