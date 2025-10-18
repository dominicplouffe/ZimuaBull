"""
Test if SELL transaction save() actually updates cash balance.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from decimal import Decimal
from zimuabull.models import Portfolio, PortfolioTransaction, TransactionType, Symbol
from datetime import date

def test_manual_sell_transaction():
    """Manually create a SELL transaction and see if cash is updated"""
    portfolio = Portfolio.objects.get(id=15)
    symbol = Symbol.objects.filter(exchange=portfolio.exchange).first()

    print(f"Portfolio: {portfolio.name}")
    print(f"Cash BEFORE: ${portfolio.cash_balance}\n")

    # Create a test SELL transaction
    print("Creating SELL transaction:")
    print(f"  Symbol: {symbol.symbol}")
    print(f"  Quantity: 0.1")
    print(f"  Price: $50.00")
    print(f"  Expected cash increase: $5.00\n")

    txn = PortfolioTransaction(
        portfolio=portfolio,
        symbol=symbol,
        transaction_type=TransactionType.SELL,
        quantity=Decimal("0.1"),
        price=Decimal("50.00"),
        transaction_date=date.today(),
        notes="TEST TRANSACTION - MANUAL SELL"
    )

    print(f"Transaction object created (pk={txn.pk})")
    print(f"Is new? {txn.pk is None}\n")

    # Call save()
    print("Calling txn.save()...")
    txn.save()
    print(f"Transaction saved (pk={txn.pk})\n")

    # Refresh portfolio from DB
    portfolio.refresh_from_db()
    print(f"Cash AFTER: ${portfolio.cash_balance}")
    print(f"Expected AFTER: ${float(portfolio.cash_balance) - 5.00 + 5.00}")

    # Clean up - delete the test transaction
    print("\nCleaning up test transaction...")
    txn.delete()
    print("Test transaction deleted")

def trace_transaction_save_path():
    """Trace the save path with debugging"""
    portfolio = Portfolio.objects.get(id=15)
    symbol = Symbol.objects.filter(exchange=portfolio.exchange).first()

    cash_before = portfolio.cash_balance

    print(f"=== TRACING SELL TRANSACTION SAVE PATH ===\n")
    print(f"Portfolio: {portfolio.name}")
    print(f"Cash before: ${cash_before}\n")

    # Temporarily add debugging to the save method
    import zimuabull.models
    original_save = zimuabull.models.PortfolioTransaction.save

    def debug_save(self, *args, **kwargs):
        print(f"[DEBUG] save() called on PortfolioTransaction")
        print(f"[DEBUG]   transaction_type: {self.transaction_type}")
        print(f"[DEBUG]   is_new (pk is None): {self.pk is None}")
        print(f"[DEBUG]   portfolio: {self.portfolio.name}")
        print(f"[DEBUG]   cash_balance before super().save(): ${self.portfolio.cash_balance}")

        # Call original save
        result = original_save(self, *args, **kwargs)

        self.portfolio.refresh_from_db()
        print(f"[DEBUG]   cash_balance after everything: ${self.portfolio.cash_balance}")

        return result

    # Monkey patch
    zimuabull.models.PortfolioTransaction.save = debug_save

    try:
        # Create test transaction
        txn = PortfolioTransaction(
            portfolio=portfolio,
            symbol=symbol,
            transaction_type=TransactionType.SELL,
            quantity=Decimal("0.1"),
            price=Decimal("50.00"),
            transaction_date=date.today(),
            notes="TEST TRANSACTION - DEBUG TRACE"
        )

        print("Calling txn.save()...\n")
        txn.save()

        portfolio.refresh_from_db()
        print(f"\n=== RESULT ===")
        print(f"Cash before: ${cash_before}")
        print(f"Cash after:  ${portfolio.cash_balance}")
        print(f"Difference:  ${portfolio.cash_balance - cash_before}")

        # Clean up
        txn.delete()

    finally:
        # Restore original
        zimuabull.models.PortfolioTransaction.save = original_save

if __name__ == "__main__":
    print("TEST 1: Manual SELL Transaction\n")
    print("=" * 80)
    test_manual_sell_transaction()

    print("\n\n")
    print("TEST 2: Trace Transaction Save Path\n")
    print("=" * 80)
    trace_transaction_save_path()
