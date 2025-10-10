from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.utils import timezone

import pandas as pd

from zimuabull.models import DaySymbol, Portfolio, PortfolioHolding, Symbol


class ToolExecutionError(Exception):
    """Raised when a tool execution cannot be completed."""


def _resolve_symbol(symbol_code: str, exchange_code: str | None = None) -> tuple[Symbol, list[str]]:
    qs = Symbol.objects.filter(symbol__iexact=symbol_code)
    warnings: list[str] = []

    if exchange_code:
        qs = qs.filter(exchange__code__iexact=exchange_code)

    if not qs.exists():
        raise ToolExecutionError(f"Symbol {symbol_code} not found" + (f" on {exchange_code}" if exchange_code else ""))

    if qs.count() > 1:
        qs = qs.order_by("-last_volume", "-accuracy", "-updated_at")
        top = qs.first()
        warnings.append(
            f"Symbol {symbol_code.upper()} exists on multiple exchanges; using {top.exchange.code}. "
            "Include an exchange code to override."
        )
        return top, warnings

    return qs.first(), warnings


def _price_history(symbol: Symbol, start: date | None = None, end: date | None = None, lookback_days: int | None = 90) -> list[dict[str, Any]]:
    if start and end is None:
        end = start

    if end is None:
        end = timezone.now().date()

    if start is None:
        if lookback_days is None:
            lookback_days = 90
        start = end - timedelta(days=lookback_days * 2)

    qs = (
        DaySymbol.objects.filter(symbol=symbol, date__gte=start, date__lte=end)
        .order_by("date")
        .values("date", "open", "high", "low", "close", "volume", "rsi", "macd", "macd_signal", "macd_histogram")
    )
    return [
        {
            "date": row["date"].isoformat(),
            "open": round(row["open"], 2),
            "high": round(row["high"], 2),
            "low": round(row["low"], 2),
            "close": round(row["close"], 2),
            "volume": int(row["volume"]),
            "rsi": round(row["rsi"], 2) if row["rsi"] is not None else None,
            "macd": round(row["macd"], 4) if row["macd"] is not None else None,
            "macd_signal": round(row["macd_signal"], 4) if row["macd_signal"] is not None else None,
            "macd_histogram": round(row["macd_histogram"], 4) if row["macd_histogram"] is not None else None,
        }
        for row in qs
    ]


def _symbol_stats(symbol: Symbol, history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {}

    latest = history[-1]
    prev = history[-2] if len(history) > 1 else latest
    change = latest["close"] - prev["close"]
    change_pct = (change / prev["close"] * 100) if prev["close"] else 0
    closes = [h["close"] for h in history]

    return {
        "latest_close": latest["close"],
        "latest_date": latest["date"],
        "change": round(change, 2),
        "change_percent": round(change_pct, 2),
        "highest_close": round(max(closes), 2),
        "lowest_close": round(min(closes), 2),
        "trend_angle": round(symbol.thirty_close_trend or 0, 2),
        "signal": symbol.obv_status,
        "latest_prediction": getattr(symbol.dayprediction_set.order_by("-date").first(), "prediction", None),
        "accuracy": round(symbol.accuracy, 4) if symbol.accuracy is not None else None,
        "last_volume": int(symbol.last_volume),
    }


def _portfolio_holdings_snapshot(portfolio: Portfolio) -> list[dict[str, Any]]:
    holdings = PortfolioHolding.objects.filter(portfolio=portfolio, status="ACTIVE").select_related("symbol", "symbol__exchange")
    snapshot = []
    for holding in holdings:
        symbol = holding.symbol
        latest_price = symbol.latest_price if symbol.latest_price is not None else Decimal(str(symbol.last_close))
        market_value = float(latest_price * holding.quantity)
        snapshot.append(
            {
                "symbol": symbol.symbol,
                "exchange": symbol.exchange.code,
                "name": symbol.name,
                "sector": symbol.sector,
                "quantity": float(holding.quantity),
                "average_cost": float(holding.average_cost),
                "market_price": float(latest_price),
                "market_value": market_value,
                "gain_loss": market_value - float(holding.average_cost * holding.quantity),
                "signal": symbol.obv_status,
            }
        )
    return snapshot


def _portfolio_sector_breakdown(holdings: list[dict[str, Any]]) -> dict[str, float]:
    breakdown: dict[str, float] = {}
    total = sum(h["market_value"] for h in holdings)
    if total == 0:
        return {}
    for holding in holdings:
        sector = holding.get("sector") or "Unknown"
        breakdown[sector] = breakdown.get(sector, 0.0) + holding["market_value"]
    return {sector: round(value / total * 100, 2) for sector, value in breakdown.items()}


def _apply_portfolio_scenario(holdings: list[dict[str, Any]], adjustments: dict[str, float]) -> dict[str, Any]:
    new_value = 0.0
    original_value = sum(h["market_value"] for h in holdings)
    impact_rows = []

    for holding in holdings:
        symbol_key = f"{holding['symbol']}:{holding['exchange']}"
        pct_change = adjustments.get(symbol_key) or adjustments.get(holding["symbol"]) or 0.0
        adjusted_price = holding["market_price"] * (1 + pct_change / 100)
        adjusted_value = adjusted_price * holding["quantity"]
        new_value += adjusted_value
        impact_rows.append(
            {
                "symbol": holding["symbol"],
                "exchange": holding["exchange"],
                "pct_change": pct_change,
                "original_value": round(holding["market_value"], 2),
                "adjusted_value": round(adjusted_value, 2),
                "value_delta": round(adjusted_value - holding["market_value"], 2),
            }
        )

    portfolio_delta = new_value - original_value
    return {
        "original_value": round(original_value, 2),
        "scenario_value": round(new_value, 2),
        "delta": round(portfolio_delta, 2),
        "delta_percent": round(portfolio_delta / original_value * 100, 2) if original_value else 0.0,
        "positions": impact_rows,
    }


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _backtest_ema_crossover(df: pd.DataFrame, fast: int, slow: int, initial_capital: float) -> dict[str, Any]:
    df = df.copy()
    df["fast_ema"] = _ema(df["close"], fast)
    df["slow_ema"] = _ema(df["close"], slow)
    df["signal"] = 0
    df.loc[df["fast_ema"] > df["slow_ema"], "signal"] = 1
    df.loc[df["fast_ema"] < df["slow_ema"], "signal"] = -1
    df["orders"] = df["signal"].diff()

    cash = initial_capital
    shares = 0.0
    trades = []

    for _, row in df.iterrows():
        price = row["close"]
        if row["orders"] == 1:  # buy signal
            if cash > 0:
                shares = cash / price
                trades.append({"action": "BUY", "price": round(price, 2), "shares": round(shares, 4), "date": row["date"].isoformat(), "reason": "EMA crossover (fast above slow)"})
                cash = 0.0
        elif row["orders"] == -1 and shares > 0:  # sell signal
            cash = shares * price
            trades.append({"action": "SELL", "price": round(price, 2), "shares": round(shares, 4), "date": row["date"].isoformat(), "reason": "EMA crossover (fast below slow)"})
            shares = 0.0

    final_price = df.iloc[-1]["close"]
    ending_value = cash + shares * final_price
    pnl = ending_value - initial_capital
    return {
        "initial_capital": initial_capital,
        "ending_value": round(ending_value, 2),
        "pnl": round(pnl, 2),
        "return_percent": round(pnl / initial_capital * 100, 2) if initial_capital else 0.0,
        "trades": trades,
    }


def _rule_based_simulation(df: pd.DataFrame, buy_threshold: Decimal, sell_threshold: Decimal, buy_shares: int, bankroll: Decimal) -> dict[str, Any]:
    cash = bankroll
    shares = Decimal("0")
    trades = []

    prev_close = Decimal(str(df.iloc[0]["close"]))

    for _, row in df.iloc[1:].iterrows():
        current_close = Decimal(str(row["close"]))
        delta = current_close - prev_close
        if delta >= buy_threshold:
            cost = current_close * buy_shares
            if cash >= cost:
                cash -= cost
                shares += Decimal(buy_shares)
                trades.append(
                    {
                        "action": "BUY",
                        "shares": buy_shares,
                        "price": float(current_close),
                        "date": row["date"].isoformat(),
                        "reason": f"Price rose by ${delta:.2f} (>= ${buy_threshold})",
                    }
                )
        elif delta <= -sell_threshold and shares > 0:
            proceeds = current_close * shares
            cash += proceeds
            trades.append(
                {
                    "action": "SELL",
                    "shares": float(shares),
                    "price": float(current_close),
                    "date": row["date"].isoformat(),
                    "reason": f"Price fell by ${delta:.2f} (<= -${sell_threshold})",
                }
            )
            shares = Decimal("0")
        prev_close = current_close

    last_price = Decimal(str(df.iloc[-1]["close"]))
    ending_value = cash + shares * last_price
    pnl = ending_value - bankroll
    return {
        "starting_bankroll": float(bankroll),
        "ending_value": float(ending_value),
        "pnl": float(pnl),
        "return_percent": float((pnl / bankroll * 100) if bankroll else Decimal("0")),
        "remaining_shares": float(shares),
        "last_price": float(last_price),
        "trades": trades,
        "days_evaluated": len(df),
    }


class ChatToolset:
    def __init__(self, user):
        self.user = user

    def tool_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_symbol_overview",
                    "description": "Fetch latest performance metrics for a given symbol, optionally including recent price history.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Ticker symbol, e.g., AAPL"},
                            "exchange": {"type": "string", "description": "Exchange code such as NASDAQ, NYSE, TSE", "nullable": True},
                            "include_history": {"type": "boolean", "default": False},
                            "history_days": {"type": "integer", "default": 30, "minimum": 5, "maximum": 365},
                        },
                        "required": ["symbol"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "compare_symbols",
                    "description": "Compare multiple symbols side-by-side across key metrics.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbols": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "symbol": {"type": "string"},
                                        "exchange": {"type": "string", "nullable": True},
                                    },
                                    "required": ["symbol"],
                                },
                                "minItems": 2,
                                "maxItems": 10,
                            },
                            "include_history": {"type": "boolean", "default": False},
                            "history_days": {"type": "integer", "default": 30, "minimum": 5, "maximum": 365},
                        },
                        "required": ["symbols"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "portfolio_overview",
                    "description": "Summarize portfolio holdings, cash, and allocation metrics for the current user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "portfolio_ids": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "nullable": True,
                            }
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "portfolio_scenario_analysis",
                    "description": "Run scenario analysis by applying percentage changes to specified holdings.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "portfolio_id": {"type": "integer", "nullable": True},
                            "adjustments": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "symbol": {"type": "string"},
                                        "exchange": {"type": "string", "nullable": True},
                                        "pct_change": {"type": "number"},
                                    },
                                    "required": ["symbol", "pct_change"],
                                },
                            },
                        },
                        "required": ["adjustments"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_strategy_backtest",
                    "description": "Backtest a technical strategy (currently EMA crossover) over a date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "exchange": {"type": "string", "nullable": True},
                            "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                            "initial_capital": {"type": "number", "default": 10000},
                            "strategy": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "enum": ["ema_crossover"]},
                                    "fast_period": {"type": "integer", "default": 20},
                                    "slow_period": {"type": "integer", "default": 50},
                                },
                                "required": ["type"],
                            },
                        },
                        "required": ["symbol", "start_date", "end_date", "strategy"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "simulate_rule_based_strategy",
                    "description": "Simulate a rule-based buy/sell strategy using daily close deltas.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "exchange": {"type": "string", "nullable": True},
                            "buy_threshold": {"type": "number", "description": "Dollar increase triggering a buy"},
                            "sell_threshold": {"type": "number", "description": "Dollar decrease triggering a sell"},
                            "buy_shares": {"type": "integer"},
                            "initial_capital": {"type": "number", "default": 1000},
                            "history_days": {"type": "integer", "default": 90, "minimum": 10, "maximum": 365},
                        },
                        "required": ["symbol", "buy_threshold", "sell_threshold", "buy_shares"],
                    },
                },
            },
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "get_symbol_overview":
            return self._symbol_overview(**arguments)
        if name == "compare_symbols":
            return self._compare_symbols(**arguments)
        if name == "portfolio_overview":
            return self._portfolio_overview(**arguments)
        if name == "portfolio_scenario_analysis":
            return self._portfolio_scenario(**arguments)
        if name == "run_strategy_backtest":
            return self._run_backtest(**arguments)
        if name == "simulate_rule_based_strategy":
            return self._simulate_rule_strategy(**arguments)
        msg = f"Unknown tool {name}"
        raise ToolExecutionError(msg)

    # Tool implementations --------------------------------------------------

    def _symbol_overview(self, symbol: str, exchange: str | None = None, include_history: bool = False, history_days: int = 30) -> dict[str, Any]:
        sym, warnings = _resolve_symbol(symbol, exchange)
        history = _price_history(sym, lookback_days=history_days)
        stats = _symbol_stats(sym, history)
        payload = {
            "symbol": sym.symbol,
            "exchange": sym.exchange.code,
            "name": sym.name,
            "stats": stats,
            "indicators": {
                "rsi": history[-1]["rsi"] if history else None,
                "macd": history[-1]["macd"] if history else None,
                "macd_signal": history[-1]["macd_signal"] if history else None,
                "macd_histogram": history[-1]["macd_histogram"] if history else None,
            },
            "history": history if include_history else [],
        }
        return {"type": "symbol_overview", "data": payload, "warnings": warnings}

    def _compare_symbols(self, symbols: list[dict[str, Any]], include_history: bool = False, history_days: int = 30) -> dict[str, Any]:
        results = []
        warnings: list[str] = []
        for entry in symbols:
            sym_code = entry.get("symbol")
            exchange = entry.get("exchange")
            sym, warning = _resolve_symbol(sym_code, exchange)
            history = _price_history(sym, lookback_days=history_days)
            stats = _symbol_stats(sym, history)
            results.append(
                {
                    "symbol": sym.symbol,
                    "exchange": sym.exchange.code,
                    "name": sym.name,
                    "stats": stats,
                    "history": history if include_history else [],
                }
            )
            warnings.extend(warning)

        return {"type": "symbol_comparison", "data": {"symbols": results}, "warnings": warnings}

    def _portfolio_overview(self, portfolio_ids: list[int] | None = None) -> dict[str, Any]:
        portfolios = Portfolio.objects.filter(user=self.user, is_active=True)
        if portfolio_ids:
            portfolios = portfolios.filter(id__in=portfolio_ids)

        data = []
        for portfolio in portfolios:
            holdings = _portfolio_holdings_snapshot(portfolio)
            sector_breakdown = _portfolio_sector_breakdown(holdings)
            data.append(
                {
                    "id": portfolio.id,
                    "name": portfolio.name,
                    "exchange": portfolio.exchange.code,
                    "cash_balance": float(portfolio.cash_balance),
                    "current_value": float(portfolio.current_value()),
                    "holdings": holdings,
                    "sector_breakdown": sector_breakdown,
                }
            )
        return {"type": "portfolio_overview", "data": {"portfolios": data}, "warnings": []}

    def _portfolio_scenario(self, adjustments: list[dict[str, Any]], portfolio_id: int | None = None) -> dict[str, Any]:
        portfolios = Portfolio.objects.filter(user=self.user, is_active=True)
        if portfolio_id:
            portfolios = portfolios.filter(id=portfolio_id)
        if not portfolios.exists():
            msg = "No portfolios found for scenario analysis."
            raise ToolExecutionError(msg)

        adjustments_map = {}
        for adj in adjustments:
            key = adj["symbol"]
            if adj.get("exchange"):
                key = f"{adj['symbol']}:{adj['exchange']}"
            adjustments_map[key] = adj["pct_change"]

        results = []
        for portfolio in portfolios:
            holdings = _portfolio_holdings_snapshot(portfolio)
            scenario = _apply_portfolio_scenario(holdings, adjustments_map)
            results.append(
                {
                    "portfolio": portfolio.name,
                    "exchange": portfolio.exchange.code,
                    "scenario": scenario,
                }
            )
        return {"type": "portfolio_scenario", "data": {"results": results}, "warnings": []}

    def _run_backtest(self, symbol: str, start_date: str, end_date: str, strategy: dict[str, Any], exchange: str | None = None, initial_capital: float = 10000) -> dict[str, Any]:
        sym, warnings = _resolve_symbol(symbol, exchange)
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError as exc:
            msg = "start_date and end_date must be in YYYY-MM-DD format"
            raise ToolExecutionError(msg) from exc

        history = _price_history(sym, start=start, end=end)
        if not history:
            msg = "No price data available for the selected period."
            raise ToolExecutionError(msg)

        df = pd.DataFrame(history)
        df["date"] = pd.to_datetime(df["date"])

        strategy_type = strategy.get("type")
        if strategy_type == "ema_crossover":
            fast = strategy.get("fast_period", 20)
            slow = strategy.get("slow_period", 50)
            result = _backtest_ema_crossover(df, fast, slow, initial_capital)
            result.update({"symbol": sym.symbol, "exchange": sym.exchange.code, "strategy": strategy})
            return {"type": "backtest", "data": result, "warnings": warnings}

        msg = f"Unsupported strategy type: {strategy_type}"
        raise ToolExecutionError(msg)

    def _simulate_rule_strategy(self, symbol: str, buy_threshold: float, sell_threshold: float, buy_shares: int, exchange: str | None = None, initial_capital: float = 1000, history_days: int = 90) -> dict[str, Any]:
        sym, warnings = _resolve_symbol(symbol, exchange)
        history = _price_history(sym, lookback_days=history_days)
        if len(history) < 5:
            msg = "Not enough historical data to simulate strategy."
            raise ToolExecutionError(msg)

        df = pd.DataFrame(history)
        df["date"] = pd.to_datetime(df["date"])
        result = _rule_based_simulation(
            df,
            Decimal(str(buy_threshold)),
            Decimal(str(sell_threshold)),
            buy_shares,
            Decimal(str(initial_capital)),
        )
        result.update({"symbol": sym.symbol, "exchange": sym.exchange.code})
        return {"type": "simulation", "data": result, "warnings": warnings}


def aggregate_tool_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    aggregated: dict[str, Any] = {
        "symbols": [],
        "comparisons": [],
        "portfolios": [],
        "scenarios": [],
        "backtests": [],
        "simulations": [],
        "warnings": [],
    }

    for result in results:
        if not isinstance(result, dict):
            continue
        if "error" in result:
            tool_name = result.get("tool", "tool")
            aggregated["warnings"].append(f"{tool_name} error: {result['error']}")
            continue
        result_type = result.get("type")
        data = result.get("data")
        warnings = result.get("warnings", [])
        aggregated["warnings"].extend(warnings)

        if result_type == "symbol_overview":
            aggregated["symbols"].append(data)
        elif result_type == "symbol_comparison":
            aggregated["comparisons"].append(data)
        elif result_type == "portfolio_overview":
            aggregated["portfolios"].extend(data.get("portfolios", []))
        elif result_type == "portfolio_scenario":
            aggregated["scenarios"].extend(data.get("results", []))
        elif result_type == "backtest":
            aggregated["backtests"].append(data)
        elif result_type == "simulation":
            aggregated["simulations"].append(data)

    return aggregated
