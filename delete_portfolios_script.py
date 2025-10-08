"""
Temporary script to delete all portfolio-related data.
Run this in Django shell or IPython with Django loaded.

Usage:
    python manage.py shell
    >>> exec(open('delete_portfolios_script.py').read())

Or copy/paste directly into IPython:
"""

from zimuabull.models import (
    Portfolio, PortfolioTransaction, PortfolioHolding,
    PortfolioSnapshot, DayTradingRecommendation
)

# Count before deletion
print("\n=== BEFORE DELETION ===")
print(f"Portfolios: {Portfolio.objects.count()}")
print(f"Transactions: {PortfolioTransaction.objects.count()}")
print(f"Holdings: {PortfolioHolding.objects.count()}")
print(f"Snapshots: {PortfolioSnapshot.objects.count()}")
print(f"Day Trading Recommendations: {DayTradingRecommendation.objects.count()}")

# Delete all (cascade will handle related records)
print("\n=== DELETING ===")

# Delete transactions first (no cascade dependencies)
deleted_transactions = PortfolioTransaction.objects.all().delete()
print(f"Deleted transactions: {deleted_transactions[0]}")

# Delete holdings (no cascade dependencies)
deleted_holdings = PortfolioHolding.objects.all().delete()
print(f"Deleted holdings: {deleted_holdings[0]}")

# Delete snapshots (no cascade dependencies)
deleted_snapshots = PortfolioSnapshot.objects.all().delete()
print(f"Deleted snapshots: {deleted_snapshots[0]}")

# Delete day trading recommendations (has symbol FK but can be deleted)
deleted_recommendations = DayTradingRecommendation.objects.all().delete()
print(f"Deleted day trading recommendations: {deleted_recommendations[0]}")

# Delete portfolios last (will cascade to any remaining related records)
deleted_portfolios = Portfolio.objects.all().delete()
print(f"Deleted portfolios: {deleted_portfolios[0]}")

# Count after deletion
print("\n=== AFTER DELETION ===")
print(f"Portfolios: {Portfolio.objects.count()}")
print(f"Transactions: {PortfolioTransaction.objects.count()}")
print(f"Holdings: {PortfolioHolding.objects.count()}")
print(f"Snapshots: {PortfolioSnapshot.objects.count()}")
print(f"Day Trading Recommendations: {DayTradingRecommendation.objects.count()}")

print("\n✅ All portfolio-related data deleted successfully!")
