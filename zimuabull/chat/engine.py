import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.db.models import Avg, Max, Min
from django.utils import timezone

from zimuabull.models import DaySymbol, Portfolio, Symbol

SYMBOL_PATTERN = re.compile(r"\b[A-Za-z]{1,5}\b")
STOPWORDS = {
    "AND", "WITH", "VS", "VERSUS", "COMPARE", "SHOW", "PLEASE", "THANKS",
    "WHAT", "WHATS", "IS", "ARE", "THE", "A", "AN", "TO", "FOR", "ON", "OF",
    "ABOUT", "TELL", "ME", "PRICE", "TODAY", "YESTERDAY", "IF", "WHEN",
    "GIVE", "GET", "CHECK", "LOOK", "UP", "DOWN", "BY", "IN", "FROM"
}


@dataclass
class SymbolInsight:
    symbol: Symbol
    prices: List[Dict] = field(default_factory=list)
    stats: Dict = field(default_factory=dict)
    summary: str = ""


@dataclass
class StrategyInstruction:
    symbol: Symbol
    bankroll: Decimal
    buy_threshold: Decimal
    sell_threshold: Decimal
    buy_shares: int
    lookback_days: int = 90


def _detect_symbols(message: str) -> List[str]:
    matches = SYMBOL_PATTERN.findall(message.upper())
    unique = []
    for token in matches:
        if token in STOPWORDS:
            continue
        if token not in unique:
            unique.append(token)
    # keep only tokens that match at least one symbol in database
    confirmed = []
    for token in unique:
        if Symbol.objects.filter(symbol__iexact=token).exists():
            confirmed.append(token)
    return confirmed


def _get_symbol(symbol_code: str, exchange_code: Optional[str] = None) -> Tuple[Optional[Symbol], bool]:
    qs = Symbol.objects.filter(symbol__iexact=symbol_code)
    if exchange_code:
        qs = qs.filter(exchange__code__iexact=exchange_code)

    if not qs.exists():
        return None, False

    if qs.count() == 1:
        return qs.first(), False

    chosen = qs.order_by("-last_volume", "-accuracy", "-updated_at").first()
    return chosen, True


def _get_price_history(symbol: Symbol, days: int = 30) -> List[Dict]:
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days * 2)
    qs = (
        DaySymbol.objects.filter(symbol=symbol, date__gte=start_date, date__lte=end_date)
        .order_by("date")
        .values("date", "close", "open", "high", "low", "volume")
    )
    return [
        {
            "date": row["date"].isoformat(),
            "open": round(row["open"], 2),
            "high": round(row["high"], 2),
            "low": round(row["low"], 2),
            "close": round(row["close"], 2),
            "volume": int(row["volume"]),
        }
        for row in qs
    ]


def _summarise_symbol(symbol: Symbol, history: List[Dict]) -> Dict:
    if not history:
        return {}

    closes = [row["close"] for row in history]
    latest = history[-1]
    previous = history[-2] if len(history) > 1 else history[-1]
    change = latest["close"] - previous["close"]
    change_pct = (change / previous["close"] * 100) if previous["close"] else 0
    high = max(closes)
    low = min(closes)

    return {
        "latest_close": latest["close"],
        "latest_date": latest["date"],
        "change": round(change, 2),
        "change_percent": round(change_pct, 2),
        "highest_close": round(high, 2),
        "lowest_close": round(low, 2),
        "trend_angle": round(symbol.thirty_close_trend, 2),
        "signal": symbol.obv_status,
        "latest_prediction": getattr(symbol.dayprediction_set.order_by("-date").first(), "prediction", None),
        "accuracy": round(symbol.accuracy, 3) if symbol.accuracy is not None else None,
    }


def _format_symbol_summary(symbol: Symbol, stats: Dict) -> str:
    latest_price = stats.get("latest_close")
    change_pct = stats.get("change_percent")
    signal = stats.get("signal")
    trend = stats.get("trend_angle")
    prediction = stats.get("latest_prediction")
    parts = [f"{symbol.symbol} ({symbol.exchange.code})"]
    if latest_price is not None:
        parts.append(f"last close ${latest_price:.2f}")
    if change_pct is not None:
        parts.append(f"{change_pct:+.2f}% vs prior close")
    if signal:
        parts.append(f"signal {signal}")
    if prediction:
        parts.append(f"prediction {prediction}")
    if trend is not None:
        parts.append(f"30D trend {trend:+.1f}°")
    return ", ".join(parts)


def _portfolio_overview(user) -> Dict:
    portfolios = Portfolio.objects.filter(user=user, is_active=True)
    if not portfolios.exists():
        return {}

    overview = []
    for portfolio in portfolios:
        holdings = portfolio.holdings.select_related("symbol")
        total_value = portfolio.current_value()
        entry_count = holdings.count()
        overview.append(
            {
                "portfolio": portfolio.name,
                "exchange": portfolio.exchange.code,
                "cash_balance": float(portfolio.cash_balance),
                "current_value": total_value,
                "active_positions": entry_count,
            }
        )
    return {"portfolios": overview}


def analyze_message(user, message: str, context: Optional[Dict] = None) -> Dict:
    """
    Inspect the user's message and return an assistant-style response using
    ZimuaBull data only (no external LLM call).
    """
    context = context or {}
    lower_msg = message.lower()
    analysis: Dict = {"symbols": [], "portfolios": None, "simulation": None, "warnings": []}
    response_lines: List[str] = []

    requested_symbols = context.get("symbols") or context.get("symbol")
    if isinstance(requested_symbols, str):
        requested_symbols = [requested_symbols]

    detected_symbols = requested_symbols or _detect_symbols(message)

    insights: List[SymbolInsight] = []

    primary_symbol = None
    for sym_code in detected_symbols:
        exchange_hint = context.get("exchange")
        symbol_obj, ambiguous = _get_symbol(sym_code, exchange_hint)
        if not symbol_obj:
            continue

        if primary_symbol is None:
            primary_symbol = symbol_obj
        if ambiguous:
            analysis["warnings"].append(
                f"Symbol {symbol_obj.symbol} exists on multiple exchanges; using {symbol_obj.exchange.code}. "
                "Specify an exchange to override."
            )

        history_days = int(context.get("history_days", 30))
        history = _get_price_history(symbol_obj, days=history_days)
        stats = _summarise_symbol(symbol_obj, history)
        summary = _format_symbol_summary(symbol_obj, stats)

        insights.append(
            SymbolInsight(
                symbol=symbol_obj,
                prices=history if "history" in lower_msg or "chart" in lower_msg or context.get("include_history") else [],
                stats=stats,
                summary=summary,
            )
        )

    simulation_summary_lines: List[str] = []
    simulation_data: Optional[Dict] = None

    strategy = _extract_strategy_instructions(message, context, primary_symbol)
    if strategy:
        simulation_data = _simulate_strategy(strategy)
        analysis["simulation"] = simulation_data
        if "error" in simulation_data:
            simulation_summary_lines.append(f"Simulation error: {simulation_data['error']}")
        else:
            pnl = simulation_data["pnl"]
            ret = simulation_data["return_percent"]
            trades = len(simulation_data.get("trades", []))
            ending = simulation_data["ending_value"]
            simulation_summary_lines.append(
                f"Simulated bankroll from ${simulation_data['starting_bankroll']:.2f} ended at ${ending:.2f} "
                f"({pnl:+.2f}, {ret:+.2f}%). Executed {trades} trades."
            )

    if insights:
        response_lines.append("Here is what I found:")
        for insight in insights:
            response_lines.append(f"- {insight.summary}")
            analysis["symbols"].append(
                {
                    "symbol": insight.symbol.symbol,
                    "exchange": insight.symbol.exchange.code,
                    "name": insight.symbol.name,
                    "stats": insight.stats,
                    "price_history": insight.prices,
                }
            )
    elif not simulation_data:
        response_lines.append("I could not match any symbols from your question.")

    if "portfolio" in lower_msg or context.get("include_portfolio"):
        overview = _portfolio_overview(user)
        if overview:
            analysis["portfolios"] = overview["portfolios"]
            response_lines.append("")
            response_lines.append("Portfolio snapshot:")
            for item in overview["portfolios"]:
                response_lines.append(
                    f"- {item['portfolio']} ({item['exchange']}): ${item['current_value']:.2f} total value, cash ${item['cash_balance']:.2f}, positions {item['active_positions']}"
                )

    if insights and "trend" in lower_msg:
        response_lines.append("")
        response_lines.append("Trend assessment:")
        for insight in insights:
            trend = insight.stats.get("trend_angle")
            if trend is not None:
                if trend > 5:
                    flavour = "uptrend"
                elif trend < -5:
                    flavour = "downtrend"
                else:
                    flavour = "sideways"
                response_lines.append(f"- {insight.symbol.symbol} is in a {flavour} ({trend:+.1f}° 30-day angle).")

    if insights and ("volume" in lower_msg or "liquidity" in lower_msg):
        response_lines.append("")
        response_lines.append("Liquidity check:")
        for insight in insights:
            history = insight.prices or _get_price_history(insight.symbol, days=10)
            if not history:
                continue
            avg_volume = sum(row["volume"] for row in history) / len(history)
            response_lines.append(f"- {insight.symbol.symbol} average daily volume ~ {avg_volume:,.0f} shares.")

    if simulation_summary_lines:
        response_lines.append("")
        response_lines.extend(simulation_summary_lines)

    if analysis["warnings"]:
        response_lines.append("")
        response_lines.append("Notes:")
        for warn in analysis["warnings"]:
            response_lines.append(f"- {warn}")

    if not insights and not simulation_summary_lines and "portfolio" not in lower_msg:
        response_lines.append("")
        response_lines.append(
            "Tip: include a ticker symbol (e.g., 'MSFT' or 'SHOP:TSE') or mention 'portfolio' for account-level analytics."
        )

    reply = "\n".join(response_lines).strip()

    return {
        "reply": reply,
        "analysis": analysis,
    }
def _parse_decimal(value: str) -> Optional[Decimal]:
    try:
        clean = value.replace(",", "")
        return Decimal(clean)
    except Exception:
        return None


def _extract_strategy_instructions(message: str, context: Dict, symbol: Optional[Symbol]) -> Optional[StrategyInstruction]:
    """
    Parse natural language for simple threshold-based buy/sell rules.
    Example phrases:
     - "if it goes up by $1 buy 10 shares"
     - "goes down by $0.25 sell all"
     - "bankroll of $1000"
    """
    if not symbol:
        return None

    lower = message.lower()
    buy_match = re.search(r"goes up[^$]*\$([0-9]+(?:\.[0-9]+)?)", lower)
    sell_match = re.search(r"goes down[^$]*\$([0-9]+(?:\.[0-9]+)?)", lower)
    shares_match = re.search(r"buy\s+([0-9]+)\s+shares", lower)
    bankroll_match = re.search(r"bankroll\s+of\s+\$([0-9,]+(?:\.[0-9]+)?)", lower) or re.search(r"starting\s+with\s+\$([0-9,]+(?:\.[0-9]+)?)", lower)

    buy_threshold = _parse_decimal(buy_match.group(1)) if buy_match else None
    sell_threshold = _parse_decimal(sell_match.group(1)) if sell_match else None
    buy_shares = int(shares_match.group(1)) if shares_match else None
    bankroll = _parse_decimal(bankroll_match.group(1)) if bankroll_match else None

    if not all([buy_threshold, sell_threshold, buy_shares, bankroll]):
        return None

    lookback_days = int(context.get("history_days", 90))

    return StrategyInstruction(
        symbol=symbol,
        bankroll=bankroll,
        buy_threshold=buy_threshold,
        sell_threshold=sell_threshold,
        buy_shares=buy_shares,
        lookback_days=lookback_days,
    )


def _simulate_strategy(instruction: StrategyInstruction) -> Dict:
    history = _get_price_history(instruction.symbol, days=instruction.lookback_days)
    if len(history) < 2:
        return {"error": "Not enough history to run simulation."}

    cash = instruction.bankroll
    shares = Decimal("0")
    trade_log = []

    previous_close = Decimal(str(history[0]["close"]))

    for day_data in history[1:]:
        current_close = Decimal(str(day_data["close"]))
        delta = current_close - previous_close
        action = None

        # Buy condition
        if delta >= instruction.buy_threshold:
            cost = current_close * Decimal(instruction.buy_shares)
            if cash >= cost:
                cash -= cost
                shares += Decimal(instruction.buy_shares)
                action = {
                    "action": "BUY",
                    "shares": instruction.buy_shares,
                    "price": float(current_close),
                    "date": day_data["date"],
                    "reason": f"Price rose by ${delta:.2f} (>= ${instruction.buy_threshold})"
                }
            else:
                action = {
                    "action": "SKIP",
                    "date": day_data["date"],
                    "reason": "Insufficient cash for buy",
                }

        # Sell condition
        elif delta <= -instruction.sell_threshold and shares > 0:
            proceeds = current_close * shares
            cash += proceeds
            action = {
                "action": "SELL",
                "shares": float(shares),
                "price": float(current_close),
                "date": day_data["date"],
                "reason": f"Price fell by ${delta:.2f} (<= -${instruction.sell_threshold})"
            }
            shares = Decimal("0")

        if action:
            trade_log.append(action)

        previous_close = current_close

    last_price = Decimal(str(history[-1]["close"]))
    final_value = cash + shares * last_price
    pnl = final_value - instruction.bankroll
    return_percent = (pnl / instruction.bankroll * 100) if instruction.bankroll > 0 else Decimal("0")

    return {
        "symbol": instruction.symbol.symbol,
        "exchange": instruction.symbol.exchange.code,
        "starting_bankroll": float(instruction.bankroll),
        "ending_value": float(final_value),
        "pnl": float(pnl),
        "return_percent": float(return_percent),
        "remaining_shares": float(shares),
        "last_price": float(last_price),
        "trades": trade_log,
        "days_evaluated": len(history),
    }
