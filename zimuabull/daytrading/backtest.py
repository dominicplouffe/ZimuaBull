from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .constants import (
    BACKTEST_SLIPPAGE_BPS,
    BACKTEST_TRANSACTION_COST_BPS,
    DEFAULT_BANKROLL,
    MAX_RECOMMENDATIONS,
)
from .dataset import Dataset
from .modeling import prepare_features_for_inference


@dataclass
class TradeResult:
    trade_date: pd.Timestamp
    symbol: str
    predicted_return: float
    actual_return: float
    net_return: float
    allocation: float
    pnl: float


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    trades: list[TradeResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def run_backtest(
    dataset: Dataset,
    model,
    trained_columns,
    imputer,
    bankroll: float = DEFAULT_BANKROLL,
    max_positions: int = MAX_RECOMMENDATIONS,
    transaction_cost_bps: float = BACKTEST_TRANSACTION_COST_BPS,
    slippage_bps: float = BACKTEST_SLIPPAGE_BPS,
) -> BacktestResult:
    df = dataset.metadata.copy()
    df["prediction"] = model.predict(prepare_features_for_inference(dataset.features, trained_columns, imputer))
    df["trade_date"] = pd.to_datetime(df["trade_date"])

    df = df.sort_values("trade_date")

    equity = []
    trades: list[TradeResult] = []
    capital = bankroll
    max_drawdown = 0.0
    peak_capital = capital
    wins = 0
    losses = 0

    cost_rate = (transaction_cost_bps + slippage_bps) / 10000.0

    for trade_date, group in df.groupby("trade_date"):
        group_sorted = group.sort_values("prediction", ascending=False).head(max_positions)
        if group_sorted.empty:
            equity.append((trade_date, capital))
            continue

        allocation = capital / max_positions
        day_pnl = 0.0

        for _, row in group_sorted.iterrows():
            actual_return = row["intraday_return"]
            if actual_return is None or np.isnan(actual_return):
                continue

            net_return = actual_return - (2 * cost_rate)
            pnl = allocation * net_return
            day_pnl += pnl

            if net_return > 0:
                wins += 1
            else:
                losses += 1

            trades.append(
                TradeResult(
                    trade_date=trade_date,
                    symbol=row["symbol"],
                    predicted_return=row["prediction"],
                    actual_return=actual_return,
                    net_return=net_return,
                    allocation=allocation,
                    pnl=pnl,
                )
            )

        capital += day_pnl
        peak_capital = max(peak_capital, capital)
        drawdown = (peak_capital - capital) / peak_capital if peak_capital > 0 else 0
        max_drawdown = max(max_drawdown, drawdown)
        equity.append((trade_date, capital))

    equity_curve = pd.Series(dict(equity), dtype=float).sort_index()

    total_return = (capital - bankroll) / bankroll if bankroll else 0

    annualized_return = 0.0
    if bankroll and len(equity_curve) >= 2:
        start_date = equity_curve.index[0]
        end_date = equity_curve.index[-1]
        total_days = (end_date - start_date).days
        if total_days > 0:
            capital_ratio = capital / bankroll
            annualized_return = capital_ratio ** (365.0 / total_days) - 1

    win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0

    daily_returns = equity_curve.pct_change().dropna()
    sharpe = (daily_returns.mean() / (daily_returns.std() + 1e-9)) * np.sqrt(252) if not daily_returns.empty else 0

    summary = {
        "starting_capital": bankroll,
        "ending_capital": capital,
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "trades": len(trades),
        "sharpe": sharpe,
    }

    return BacktestResult(equity_curve=equity_curve, trades=trades, summary=summary)
