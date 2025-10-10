from datetime import timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from celery import shared_task

from zimuabull.daytrading.backtest import run_backtest
from zimuabull.daytrading.constants import (
    AUTONOMOUS_USER_ID,
    MAX_RECOMMENDATIONS,
)
from zimuabull.daytrading.dataset import load_dataset
from zimuabull.daytrading.feature_builder import (
    build_features_for_date,
    update_labels_for_date,
)
from zimuabull.daytrading.modeling import save_model, train_regression_model
from zimuabull.daytrading.trading_engine import (
    close_all_positions,
    execute_recommendations,
    generate_recommendations,
    get_open_day_trade_positions,
    get_portfolios_for_user,
    monitor_positions,
)
from zimuabull.models import (
    DayTradePosition,
    DayTradePositionStatus,
    DayTradingRecommendation,
    FeatureSnapshot,
)

NY_TZ = ZoneInfo("America/New_York")


def _is_trading_day() -> bool:
    now = timezone.now().astimezone(NY_TZ)
    return now.weekday() < 5


def _market_window_open() -> bool:
    now = timezone.now().astimezone(NY_TZ)
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def _coerce_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _within_entry_window() -> bool:
    now = timezone.now().astimezone(NY_TZ)
    target = now.replace(hour=9, minute=15, second=0, microsecond=0)
    start = target - timedelta(minutes=5)
    end = target + timedelta(minutes=5)
    return start <= now <= end


@shared_task(bind=True, ignore_result=False, queue="pidashtasks")
def run_morning_trading_session(self):
    if not _is_trading_day():
        return {"status": "skipped", "reason": "market_closed"}

    if not _within_entry_window():
        return {"status": "skipped", "reason": "outside_entry_window"}

    trade_date = timezone.now().astimezone(NY_TZ).date()
    results = []

    for portfolio in get_portfolios_for_user(AUTONOMOUS_USER_ID):
        portfolio_result = {
            "portfolio": portfolio.id,
            "exchange": portfolio.exchange.code,
        }

        if DayTradePosition.objects.filter(portfolio=portfolio, trade_date=trade_date).exists():
            portfolio_result.update({"status": "skipped", "reason": "already_executed"})
            results.append(portfolio_result)
            continue

        bankroll = float(portfolio.cash_balance)
        if bankroll <= 0:
            portfolio_result.update({"status": "skipped", "reason": "insufficient_cash"})
            results.append(portfolio_result)
            continue

        recommendations = generate_recommendations(
            trade_date=trade_date,
            max_positions=MAX_RECOMMENDATIONS,
            bankroll=bankroll,
            exchange_filter=portfolio.exchange.code,
        )

        positions = execute_recommendations(recommendations, portfolio, trade_date)
        portfolio.refresh_from_db()

        portfolio_result.update(
            {
                "status": "completed",
                "recommendations": len(recommendations),
                "executed_positions": len(positions),
                "cash_balance": float(portfolio.cash_balance),
            }
        )
        results.append(portfolio_result)

    return {
        "trade_date": str(trade_date),
        "portfolios": results,
    }


@shared_task(bind=True, ignore_result=True, queue="pidashtasks")
def monitor_intraday_positions(self):
    if not _market_window_open():
        return
    for portfolio in get_portfolios_for_user(AUTONOMOUS_USER_ID):
        monitor_positions(portfolio)


@shared_task(bind=True, ignore_result=False, queue="pidashtasks")
def close_intraday_positions(self):
    if not _is_trading_day():
        return {"status": "skipped", "reason": "market_closed"}

    results = []
    for portfolio in get_portfolios_for_user(AUTONOMOUS_USER_ID):
        open_positions = get_open_day_trade_positions(portfolio)
        close_all_positions(portfolio)
        portfolio.refresh_from_db()
        results.append(
            {
                "portfolio": portfolio.id,
                "closed_positions": len(open_positions),
                "cash_balance": float(portfolio.cash_balance),
            }
        )

    return {
        "portfolios": results,
    }


@shared_task(bind=True, ignore_result=False, queue="pidashtasks")
def generate_daily_feature_snapshots(self):
    now = timezone.now().astimezone(NY_TZ)
    if now.weekday() >= 5:
        return {"status": "skipped", "reason": "weekend"}

    trade_date = now.date()
    processed = build_features_for_date(trade_date, overwrite=True)

    return {
        "trade_date": str(trade_date),
        "snapshots_processed": processed,
    }


@shared_task(bind=True, ignore_result=False, queue="pidashtasks")
def complete_daily_feature_labels(self):
    now = timezone.now().astimezone(NY_TZ)
    if now.weekday() >= 5:
        return {"status": "skipped", "reason": "weekend"}

    trade_date = now.date()
    updated = update_labels_for_date(trade_date)

    return {
        "trade_date": str(trade_date),
        "snapshots_updated": updated,
    }


@shared_task(bind=True, ignore_result=False, queue="pidashtasks")
def weekly_model_refresh(self):
    now = timezone.now().astimezone(NY_TZ)
    if now.weekday() not in (5, 6):  # run on weekends to stay ahead of week
        return {"status": "skipped", "reason": "outside_weekend"}

    try:
        dataset = load_dataset()
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}

    if dataset.features.empty:
        return {"status": "skipped", "reason": "no_training_data"}

    try:
        model, metrics, feature_columns = train_regression_model(dataset)
        save_model(model, metrics, feature_columns)
        backtest_result = run_backtest(dataset, model, feature_columns)
    except ValueError as exc:
        return {"status": "skipped", "reason": str(exc)}
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}

    summary = {key: _coerce_float(value) for key, value in backtest_result.summary.items()}
    return {
        "status": "trained",
        "samples": metrics.get("n_samples"),
        "model_metrics": metrics,
        "backtest": summary,
    }


@shared_task(bind=True, ignore_result=False, queue="pidashtasks")
def daily_performance_report(self):
    now = timezone.now().astimezone(NY_TZ)
    if _market_window_open():
        return {"status": "skipped", "reason": "market_open"}

    trade_date = now.date()
    positions = DayTradePosition.objects.filter(trade_date=trade_date)
    if not positions.exists():
        return {"status": "skipped", "reason": "no_positions"}

    total_pnl = 0.0
    wins = 0
    losses = 0
    for position in positions:
        exit_price = float(position.exit_price or position.entry_price)
        entry_price = float(position.entry_price)
        shares = float(position.shares)
        pnl = (exit_price - entry_price) * shares
        total_pnl += pnl
        if pnl >= 0:
            wins += 1
        else:
            losses += 1

    win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0.0

    return {
        "trade_date": str(trade_date),
        "positions": positions.count(),
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 3),
        "wins": wins,
        "losses": losses,
    }


@shared_task(bind=True, ignore_result=False, queue="pidashtasks")
def daily_trading_health_check(self):
    now = timezone.now().astimezone(NY_TZ)
    trade_date = now.date()

    open_positions = DayTradePosition.objects.filter(trade_date=trade_date, status=DayTradePositionStatus.OPEN)
    recommendations = DayTradingRecommendation.objects.filter(recommendation_date=trade_date)
    orphan_recommendations = recommendations.exclude(symbol__day_trade_positions__trade_date=trade_date)
    stale_snapshots = FeatureSnapshot.objects.filter(trade_date=trade_date, label_ready=False).count()

    status = "ok"
    warnings = []

    if open_positions.exists() and not _market_window_open():
        status = "warning"
        warnings.append(f"{open_positions.count()} positions remain open after market hours")

    if orphan_recommendations.exists():
        status = "warning"
        warnings.append(f"{orphan_recommendations.count()} recommendations produced no positions")

    if stale_snapshots:
        status = "warning"
        warnings.append(f"{stale_snapshots} feature snapshots missing labels")

    return {
        "status": status,
        "open_positions": open_positions.count(),
        "recommendations": recommendations.count(),
        "orphan_recommendations": orphan_recommendations.count(),
        "stale_snapshots": stale_snapshots,
        "warnings": warnings,
    }


@shared_task(bind=True, ignore_result=False, queue="pidashtasks")
def weekly_portfolio_review(self):
    from zimuabull.services.portfolio_review import generate_weekly_portfolio_report
    report = generate_weekly_portfolio_report()
    self.app.log.get_default_logger().info("Weekly portfolio review:\\n%s", report)
    return {"report": report}
