from typing import Optional

from django.db import transaction

from zimuabull.models import (
    DayTradePosition,
    Portfolio,
    PortfolioSnapshot,
    PortfolioTransaction,
    PortfolioHolding,
)


def delete_portfolio(portfolio_id: int, *, user_id: Optional[int] = None) -> dict:
    """
    Remove a portfolio and all of its associated data (transactions, holdings, snapshots, day-trade positions).

    Args:
        portfolio_id: ID of the portfolio to delete.
        user_id: Optional user id to enforce ownership check.

    Returns:
        dict of counts showing what was deleted.

    Raises:
        Portfolio.DoesNotExist: if portfolio not found (or does not belong to user when user_id provided).
    """

    queryset = Portfolio.objects.filter(id=portfolio_id)
    if user_id is not None:
        queryset = queryset.filter(user_id=user_id)

    portfolio = queryset.select_related("user").first()
    if portfolio is None:
        raise Portfolio.DoesNotExist(f"Portfolio {portfolio_id} not found.")

    with transaction.atomic():
        transactions_deleted, _ = PortfolioTransaction.objects.filter(portfolio=portfolio).delete()
        holdings_deleted, _ = PortfolioHolding.objects.filter(portfolio=portfolio).delete()
        snapshots_deleted, _ = PortfolioSnapshot.objects.filter(portfolio=portfolio).delete()
        positions_deleted, _ = DayTradePosition.objects.filter(portfolio=portfolio).delete()
        portfolio.delete()

    return {
        "portfolio_id": portfolio_id,
        "transactions_deleted": transactions_deleted,
        "holdings_deleted": holdings_deleted,
        "snapshots_deleted": snapshots_deleted,
        "day_trade_positions_deleted": positions_deleted,
    }
