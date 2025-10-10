from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional

from django.db.models import Avg, F, Q
from django.utils import timezone

from zimuabull.daytrading.constants import (
    MAX_POSITION_PERCENT,
    MAX_RECOMMENDATIONS,
    PER_TRADE_RISK_FRACTION,
)
from decimal import Decimal

from zimuabull.models import DayTradePosition, Portfolio, PortfolioSnapshot


@dataclass
class PortfolioMetrics:
    portfolio: Portfolio
    performance_pct: float
    start_value: float
    end_value: float
    positions_taken: int
    closed_positions: int
    win_rate: Optional[float]
    avg_return: Optional[float]
    total_return: Optional[float]


def _portfolio_value(portfolio: Portfolio, target_date: date) -> float:
    snapshot = (
        PortfolioSnapshot.objects.filter(portfolio=portfolio, date__lte=target_date)
        .order_by("-date")
        .first()
    )
    if snapshot:
        return float(snapshot.total_value)
    return float(portfolio.current_value())


def _compute_metrics(portfolio: Portfolio, start_date: date, end_date: date) -> PortfolioMetrics:
    end_value = _portfolio_value(portfolio, end_date)

    positions = DayTradePosition.objects.filter(
        portfolio=portfolio,
        trade_date__range=(start_date, end_date),
    )

    closed = positions.exclude(exit_price__isnull=True)
    positioned = positions.count()
    closed_count = closed.count()

    win_rate = None
    avg_return = None
    total_return = None

    pnl_total = Decimal("0")
    if closed_count:
        wins = closed.filter(exit_price__gt=F("entry_price")).count()
        win_rate = wins / closed_count

        returns = closed.annotate(
            pct_return=((F("exit_price") - F("entry_price")) / F("entry_price")) * 100
        )
        avg_return = returns.aggregate(avg=Avg("pct_return"))["avg"]
        pnl_total = sum(
            (position.exit_price - position.entry_price) * position.shares
            for position in closed
        )
        total_return = returns.aggregate(sum=Avg("pct_return"))["sum"]

    print('0-----', total_return)
    snapshot_start = _portfolio_value(portfolio, start_date)
    if snapshot_start:
        start_value = snapshot_start
    else:
        start_value = float(Decimal(str(end_value)) - pnl_total)
        if start_value <= 0:
            start_value = end_value

    performance_pct = 0.0
    if start_value:
        performance_pct = ((end_value - start_value) / start_value) * 100

    return PortfolioMetrics(
        portfolio=portfolio,
        performance_pct=performance_pct,
        start_value=start_value,
        end_value=end_value,
        positions_taken=positioned,
        closed_positions=closed_count,
        win_rate=win_rate,
        avg_return=avg_return,
        total_return=total_return,
    )


def _recommendations_for_metrics(metrics: PortfolioMetrics) -> Dict[str, List[str]]:
    human: List[str] = []
    codex: List[str] = []
    pct = metrics.performance_pct

    if pct <= -2:
        human.append(
            "- Increase the minimum confidence threshold for intraday entries to reduce marginal trades."
        )
        codex.append(
            "Edit `generate_recommendations` in `zimuabull/daytrading/trading_engine.py` so that it filters out candidates with `confidence_score < 70` before sizing positions."
        )

        human.append(
            f"- Reduce per-trade risk budget from {PER_TRADE_RISK_FRACTION:.3f} to 0.015 to limit downside on new entries."
        )
        codex.append(
            "Update the constant `PER_TRADE_RISK_FRACTION` in `zimuabull/daytrading/constants.py` to `0.015`."
        )

        if metrics.win_rate is not None and metrics.win_rate < 0.5:
            human.append(
                "- Add a liquidity gate (~$5M average dollar volume) to avoid thinly traded names."
            )
            codex.append(
                "In `generate_recommendations`, compute average dollar volume over the last 10 days and skip tickers with average dollar volume below 5_000_000."
            )

        human.append(
            "- Tighten stop-loss handling by capping stop distance at 1.0% for high volatility symbols."
        )
        codex.append(
            "Adjust `_calculate_stop_target` in `zimuabull/daytrading/trading_engine.py` to clamp the stop-loss multiplier so that `stop_price = entry_price * 0.99` when `atr / entry_price > 0.02`."
        )
    elif pct >= 2:
        human.append("- Portfolio gained >2%; maintain current entry criteria.")
        if metrics.avg_return and metrics.avg_return < 1:
            human.append("- Consider nudging profit targets to 2.5% to capture more upside while momentum persists.")
            codex.append(
                "In `_calculate_stop_target`, increase the base target multiplier from 1.02 to 1.025 when `predicted_return > 0.04`."
            )
        else:
            human.append("- No algorithm modifications needed; continue monitoring next week.")
    else:
        human.append("- Neutral performance. Investigate sharper filters without increasing risk.")
        human.append("- Evaluate stronger RSI divergence or prediction thresholds for candidate selection.")
        codex.append(
            "Modify `_calculate_scores` in `zimuabull/views.py` (DayTradingRecommendations) so that RSI contributes full technical points only when 45 <= RSI <= 60 and reduce points outside that band."
        )

    return {"human": human, "codex": codex}


def generate_weekly_portfolio_report(reference_date: Optional[date] = None) -> str:
    reference_date = reference_date or timezone.now().date()
    end_date = reference_date
    start_date = end_date - timedelta(days=7)

    portfolios = Portfolio.objects.filter(is_active=True).select_related("exchange", "user")

    lines: List[str] = []
    lines.append(f"# Weekly Portfolio Trading Review ({end_date.isoformat()})")
    lines.append("")

    for portfolio in portfolios:
        metrics = _compute_metrics(portfolio, start_date, end_date)
        status = "Loss" if metrics.performance_pct <= -2 else "Gain" if metrics.performance_pct >= 2 else "Neutral"

        lines.append(f"## Portfolio: {portfolio.name} ({portfolio.exchange.code})")
        lines.append("")
        lines.append(f"- Owner: `{portfolio.user.username}`")
        lines.append(f"- Performance: {metrics.performance_pct:+.2f}% ({status})")
        lines.append(f"- Start Value: ${metrics.start_value:,.2f}")
        lines.append(f"- End Value: ${metrics.end_value:,.2f}")
        lines.append("")
        lines.append("### Day Trading Summary")
        lines.append(f"- Positions Opened: {metrics.positions_taken}")
        lines.append(f"- Positions Closed: {metrics.closed_positions}")
        if metrics.win_rate is not None:
            lines.append(f"- Win Rate: {metrics.win_rate * 100:.1f}%")
        if metrics.avg_return is not None:
            lines.append(f"- Average Closed Return: {metrics.avg_return:.2f}%")
        lines.append("")
        lines.append("### Recommendations")
        rec_bundle = _recommendations_for_metrics(metrics)
        lines.extend(rec_bundle["human"])
        lines.append("")
        lines.append("### Implementation Checklist")
        lines.append("1. Apply the Codex instructions listed below for this portfolio.")
        lines.append("2. Regenerate model features via `python manage.py generate_daytrading_features --date <next_trading_day>` if thresholds change.")
        lines.append("3. Retrain the model with `python manage.py train_daytrading_model` after parameter updates.")
        lines.append("4. Deploy changes and monitor Monday's trading session closely.")
        lines.append("")
        if rec_bundle["codex"]:
            lines.append("### Codex Prompt")
            lines.append("```")
            lines.append(f"# Portfolio {portfolio.name} ({portfolio.exchange.code}) adjustments")
            lines.extend(rec_bundle["codex"])
            lines.append("```")
            lines.append("")

    lines.append("---")
    lines.append("Generated automatically. Share the Codex prompts above with the automation agent to implement changes.")

    return "\n".join(lines)
