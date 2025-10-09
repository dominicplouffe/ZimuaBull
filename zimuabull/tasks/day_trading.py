from zoneinfo import ZoneInfo

from celery import shared_task
from django.utils import timezone

from zimuabull.daytrading.constants import (
    AUTONOMOUS_USER_ID,
    MAX_RECOMMENDATIONS,
)
from zimuabull.daytrading.trading_engine import (
    close_all_positions,
    execute_recommendations,
    generate_recommendations,
    get_open_day_trade_positions,
    get_portfolio_for_user,
    monitor_positions,
)
from zimuabull.models import DayTradePosition

NY_TZ = ZoneInfo("America/New_York")


def _is_trading_day() -> bool:
    now = timezone.now().astimezone(NY_TZ)
    return now.weekday() < 5


def _market_window_open() -> bool:
    now = timezone.now().astimezone(NY_TZ)
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


@shared_task(bind=True, ignore_result=False, queue="pidashtasks")
def run_morning_trading_session(self):
    if not _is_trading_day():
        return {"status": "skipped", "reason": "market_closed"}

    portfolio = get_portfolio_for_user(AUTONOMOUS_USER_ID)
    trade_date = timezone.now().astimezone(NY_TZ).date()

    if DayTradePosition.objects.filter(portfolio=portfolio, trade_date=trade_date).exists():
        return {"status": "skipped", "reason": "already_executed"}

    bankroll = float(portfolio.cash_balance)

    recommendations = generate_recommendations(
        trade_date=trade_date,
        max_positions=MAX_RECOMMENDATIONS,
        bankroll=bankroll,
        exchange_filter=portfolio.exchange.code,
    )

    positions = execute_recommendations(recommendations, portfolio, trade_date)

    return {
        "portfolio": portfolio.id,
        "trade_date": str(trade_date),
        "recommendations": len(recommendations),
        "executed_positions": len(positions),
        "cash_balance": float(portfolio.cash_balance),
    }


@shared_task(bind=True, ignore_result=True, queue="pidashtasks")
def monitor_intraday_positions(self):
    if not _market_window_open():
        return
    portfolio = get_portfolio_for_user(AUTONOMOUS_USER_ID)
    monitor_positions(portfolio)


@shared_task(bind=True, ignore_result=False, queue="pidashtasks")
def close_intraday_positions(self):
    if not _is_trading_day():
        return {"status": "skipped", "reason": "market_closed"}

    portfolio = get_portfolio_for_user(AUTONOMOUS_USER_ID)
    open_positions = get_open_day_trade_positions(portfolio)
    close_all_positions(portfolio)

    return {
        "portfolio": portfolio.id,
        "closed_positions": len(open_positions),
        "cash_balance": float(portfolio.cash_balance),
    }
