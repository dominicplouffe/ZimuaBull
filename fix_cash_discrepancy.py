"""
Fix the cash balance discrepancy by calculating correct balance from all transactions.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from decimal import Decimal
from zimuabull.models import Portfolio, PortfolioTransaction, TransactionType

def fix_portfolio_cash(portfolio_id=15, dry_run=True):
    """Recalculate and fix portfolio cash balance based on transaction history"""
    portfolio = Portfolio.objects.get(id=portfolio_id)

    print(f"Portfolio: {portfolio.name}")
    print(f"Current Cash Balance: ${portfolio.cash_balance}")
    print()

    # Calculate correct cash from all transactions
    transactions = PortfolioTransaction.objects.filter(
        portfolio=portfolio
    ).order_by('transaction_date', 'created_at')

    calculated_cash = Decimal("0")

    print(f"Analyzing {transactions.count()} transactions...\n")

    for txn in transactions:
        if txn.transaction_type == TransactionType.DEPOSIT:
            calculated_cash += txn.amount
        elif txn.transaction_type == TransactionType.WITHDRAWAL:
            calculated_cash -= txn.amount
        elif txn.transaction_type == TransactionType.BUY:
            calculated_cash -= (txn.quantity * txn.price)
        elif txn.transaction_type == TransactionType.SELL:
            calculated_cash += (txn.quantity * txn.price)

    print(f"Calculated Cash (from transactions): ${calculated_cash}")
    print(f"Current Portfolio Cash:               ${portfolio.cash_balance}")
    print(f"Discrepancy:                          ${calculated_cash - portfolio.cash_balance}")
    print()

    if abs(calculated_cash - portfolio.cash_balance) > Decimal("0.01"):
        print(f"⚠️  Discrepancy found: ${calculated_cash - portfolio.cash_balance}")

        if dry_run:
            print("\n[DRY RUN] Would update portfolio cash_balance to:", calculated_cash)
            print("Run with dry_run=False to apply the fix")
        else:
            old_balance = portfolio.cash_balance
            portfolio.cash_balance = calculated_cash
            portfolio.save(update_fields=["cash_balance", "updated_at"])
            print(f"\n✅ Fixed! Updated cash balance from ${old_balance} to ${calculated_cash}")
    else:
        print("✅ Cash balance is accurate!")

if __name__ == "__main__":
    import sys

    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == "--apply":
        dry_run = False
        print("=" * 80)
        print("APPLYING FIX (NOT A DRY RUN)")
        print("=" * 80)
        print()

    fix_portfolio_cash(dry_run=dry_run)

    if dry_run:
        print("\n" + "=" * 80)
        print("This was a DRY RUN. To apply the fix, run:")
        print("  python fix_cash_discrepancy.py --apply")
        print("=" * 80)
