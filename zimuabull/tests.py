from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from zimuabull.daytrading.trading_engine import (
    Recommendation,
    close_all_positions,
    execute_recommendations,
)
from zimuabull.models import (
    DayTradePosition,
    DayTradePositionStatus,
    Exchange,
    Portfolio,
    PortfolioSnapshot,
    PortfolioTransaction,
    Symbol,
)


class TradingEngineTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="pass")
        self.exchange = Exchange.objects.create(name="NASDAQ", code="NASDAQ", country="USA")
        self.symbol = Symbol.objects.create(
            name="Acme Corp",
            symbol="ACME",
            exchange=self.exchange,
            last_open=100,
            last_close=100,
            last_volume=1_000_000,
            obv_status="BUY",
            thirty_close_trend=5.0,
            close_bucket="UP",
        )
        self.portfolio = Portfolio.objects.create(
            name="Growth",
            user=self.user,
            exchange=self.exchange,
            cash_balance=Decimal("10000.00"),
        )

    def _recommendation(self, entry_price=100.0, target_price=110.0, stop_price=95.0, allocation=Decimal("1000")):
        shares = allocation / Decimal(str(entry_price))
        return Recommendation(
            symbol=self.symbol,
            predicted_return=0.05,
            confidence_score=85.0,
            entry_price=entry_price,
            target_price=target_price,
            stop_price=stop_price,
            allocation=allocation,
            shares=shares,
            atr=1.5,
            features={},
        )

    @patch("zimuabull.daytrading.trading_engine.fetch_live_price")
    def test_execute_and_close_positions_updates_cash_balance(self, mock_fetch_price):
        mock_fetch_price.side_effect = [None, 110.0]
        rec = self._recommendation(entry_price=100.0, target_price=110.0, stop_price=95.0)
        trade_date = timezone.now().date()

        positions = execute_recommendations([rec], self.portfolio, trade_date)

        self.portfolio.refresh_from_db()
        self.symbol.refresh_from_db()

        assert len(positions) == 1
        position = positions[0]
        assert position.status == DayTradePositionStatus.OPEN
        assert position.shares == Decimal("10")
        assert self.portfolio.cash_balance == Decimal("9000.00")
        assert self.symbol.latest_price == Decimal("100.00")

        close_all_positions(self.portfolio)
        self.portfolio.refresh_from_db()

        assert self.portfolio.cash_balance == Decimal("10100.00")
        position.refresh_from_db()
        assert position.status == DayTradePositionStatus.CLOSED
        assert position.exit_price == Decimal("110.00")

        assert PortfolioTransaction.objects.filter(portfolio=self.portfolio).count() == 2
        assert PortfolioSnapshot.objects.filter(portfolio=self.portfolio, date=timezone.now().date()).exists()

    @patch("zimuabull.daytrading.trading_engine.fetch_live_price", return_value=None)
    def test_execute_recommendations_idempotent(self, _mock_fetch_price):
        rec = self._recommendation()
        trade_date = timezone.now().date()

        execute_recommendations([rec], self.portfolio, trade_date)
        cash_after_first = Portfolio.objects.get(id=self.portfolio.id).cash_balance

        execute_recommendations([rec], self.portfolio, trade_date)

        assert DayTradePosition.objects.filter(portfolio=self.portfolio).count() == 1
        assert Portfolio.objects.get(id=self.portfolio.id).cash_balance == cash_after_first
