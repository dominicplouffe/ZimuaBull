"""
Helper functions for formatting stock market data for LLM consumption.

These functions prepare data in a way that's easy for LLMs like Claude and ChatGPT
to understand and reason about.
"""

from datetime import datetime, timedelta
from .models import Symbol, DaySymbol, DayPrediction, Portfolio


def format_symbol_for_llm(symbol, include_history=False, history_days=30):
    """
    Format a symbol's data into a natural language summary for LLMs.

    Args:
        symbol: Symbol model instance
        include_history: Whether to include historical price data (enables moving averages, etc.)
        history_days: Number of days of history to include (default 30, max 365)

    Returns:
        dict: Contains summary text and structured data with optional historical prices
    """
    # Get latest prediction
    latest_prediction = DayPrediction.objects.filter(symbol=symbol).order_by('-date').first()

    # Get recent price action
    recent_days = DaySymbol.objects.filter(symbol=symbol).order_by('-date')[:min(history_days, 365)]

    # Build summary
    summary_parts = []
    summary_parts.append(f"{symbol.name} ({symbol.symbol}) on {symbol.exchange.code}")
    summary_parts.append(f"Current Price: ${symbol.last_close:.2f}")
    summary_parts.append(f"Trading Signal: {symbol.obv_status}")

    if symbol.thirty_close_trend > 5:
        summary_parts.append(f"Strong uptrend ({symbol.thirty_close_trend:.1f}° angle)")
    elif symbol.thirty_close_trend < -5:
        summary_parts.append(f"Strong downtrend ({symbol.thirty_close_trend:.1f}° angle)")
    else:
        summary_parts.append(f"Sideways movement ({symbol.thirty_close_trend:.1f}° angle)")

    if latest_prediction:
        summary_parts.append(f"AI Prediction: {latest_prediction.prediction}")
        if symbol.accuracy:
            summary_parts.append(f"Model Accuracy: {symbol.accuracy:.1%}")

    summary = ". ".join(summary_parts) + "."

    result = {
        "summary": summary,
        "symbol": symbol.symbol,
        "name": symbol.name,
        "exchange": symbol.exchange.code,
        "current_price": float(symbol.last_close),
        "signal": symbol.obv_status,
        "trend_angle": float(symbol.thirty_close_trend),
        "prediction": latest_prediction.prediction if latest_prediction else None,
        "accuracy": float(symbol.accuracy) if symbol.accuracy else None,
        "volume": symbol.last_volume,
        "days_of_data": recent_days.count()
    }

    # Add historical price data if requested (enables calculations like moving averages)
    if include_history and recent_days:
        historical_data = []
        for day in recent_days:
            day_data = {
                "date": day.date.isoformat(),
                "open": float(day.open),
                "high": float(day.high),
                "low": float(day.low),
                "close": float(day.close),
                "volume": day.volume,
                "obv": day.obv,
                "obv_signal_sum": day.obv_signal_sum
            }

            # Include technical indicators if available
            if day.rsi is not None:
                day_data["rsi"] = float(day.rsi)
            if day.macd is not None:
                day_data["macd"] = float(day.macd)
                day_data["macd_signal"] = float(day.macd_signal) if day.macd_signal else None
                day_data["macd_histogram"] = float(day.macd_histogram) if day.macd_histogram else None

            historical_data.append(day_data)

        # Sort by date (oldest to newest) for easier calculations
        historical_data.reverse()

        result["historical_data"] = historical_data
        result["historical_summary"] = (
            f"Historical data: {len(historical_data)} trading days from {historical_data[0]['date']} "
            f"to {historical_data[-1]['date']}. "
            f"Price range: ${min(d['low'] for d in historical_data):.2f} - "
            f"${max(d['high'] for d in historical_data):.2f}."
        )

        # Calculate simple statistics for LLM
        closes = [d['close'] for d in historical_data]
        result["price_statistics"] = {
            "min": round(min(closes), 2),
            "max": round(max(closes), 2),
            "avg": round(sum(closes) / len(closes), 2),
            "first": closes[0],  # Oldest
            "last": closes[-1],  # Newest (current)
            "change": round(closes[-1] - closes[0], 2),
            "change_percent": round(((closes[-1] - closes[0]) / closes[0] * 100), 2) if closes[0] != 0 else 0
        }

        # Add technical indicators summary if available
        latest_day = recent_days.first()  # Most recent
        tech_indicators = {}
        if latest_day.rsi is not None:
            tech_indicators["rsi"] = {
                "value": float(latest_day.rsi),
                "interpretation": (
                    "Overbought (>70)" if latest_day.rsi > 70 else
                    "Oversold (<30)" if latest_day.rsi < 30 else
                    "Neutral (30-70)"
                )
            }
        if latest_day.macd is not None:
            tech_indicators["macd"] = {
                "macd_line": float(latest_day.macd),
                "signal_line": float(latest_day.macd_signal) if latest_day.macd_signal else None,
                "histogram": float(latest_day.macd_histogram) if latest_day.macd_histogram else None,
                "interpretation": (
                    "Bullish (MACD > Signal)" if latest_day.macd_histogram and latest_day.macd_histogram > 0 else
                    "Bearish (MACD < Signal)" if latest_day.macd_histogram and latest_day.macd_histogram < 0 else
                    "Neutral"
                )
            }

        if tech_indicators:
            result["technical_indicators"] = tech_indicators

        # Add note for LLM about calculations
        result["calculation_note"] = (
            "Historical data includes OHLCV, OBV, RSI, and MACD values. "
            "You can calculate moving averages and other custom indicators. "
            "RSI values: <30 oversold, >70 overbought. "
            "MACD: Positive histogram = bullish, negative = bearish."
        )

    return result


def format_portfolio_for_llm(portfolio):
    """
    Format a portfolio's data into a natural language summary for LLMs.

    Args:
        portfolio: Portfolio model instance

    Returns:
        dict: Contains summary text and structured data
    """
    total_invested = portfolio.total_invested()
    current_value = portfolio.current_value()
    gain_loss = portfolio.total_gain_loss()
    gain_loss_pct = portfolio.total_gain_loss_percent()

    holdings = portfolio.holdings.filter(status='ACTIVE')

    # Build summary
    summary_parts = []
    summary_parts.append(f"Portfolio: {portfolio.name} ({portfolio.exchange.code})")
    summary_parts.append(f"Total Invested: ${total_invested:,.2f}")
    summary_parts.append(f"Current Value: ${current_value:,.2f}")

    if gain_loss >= 0:
        summary_parts.append(f"Gain: ${gain_loss:,.2f} (+{gain_loss_pct:.2f}%)")
    else:
        summary_parts.append(f"Loss: ${abs(gain_loss):,.2f} ({gain_loss_pct:.2f}%)")

    summary_parts.append(f"Holdings: {holdings.count()} active positions")

    # Add top performers
    holdings_list = list(holdings)
    if holdings_list:
        holdings_list.sort(key=lambda h: h.gain_loss_percent(), reverse=True)
        best = holdings_list[0]
        summary_parts.append(
            f"Best: {best.symbol.symbol} (+{best.gain_loss_percent():.1f}%)"
        )
        if len(holdings_list) > 1:
            worst = holdings_list[-1]
            summary_parts.append(
                f"Worst: {worst.symbol.symbol} ({worst.gain_loss_percent():.1f}%)"
            )

    summary = ". ".join(summary_parts) + "."

    # Detailed holdings
    holdings_data = []
    for holding in holdings:
        holdings_data.append({
            "symbol": holding.symbol.symbol,
            "name": holding.symbol.name,
            "quantity": float(holding.quantity),
            "purchase_price": float(holding.purchase_price),
            "current_price": float(holding.symbol.last_close),
            "cost_basis": holding.cost_basis(),
            "current_value": holding.current_value(),
            "gain_loss": holding.gain_loss(),
            "gain_loss_percent": holding.gain_loss_percent(),
            "days_held": holding.days_held(),
            "signal": holding.symbol.obv_status
        })

    return {
        "summary": summary,
        "portfolio_name": portfolio.name,
        "exchange": portfolio.exchange.code,
        "country": portfolio.exchange.country,
        "total_invested": float(total_invested),
        "current_value": float(current_value),
        "gain_loss": float(gain_loss),
        "gain_loss_percent": float(gain_loss_pct),
        "holdings_count": holdings.count(),
        "holdings": holdings_data
    }


def format_market_overview_for_llm(exchange_code=None):
    """
    Format market overview data for LLM consumption.

    Args:
        exchange_code: Optional exchange code to filter by

    Returns:
        dict: Market overview data
    """
    symbols = Symbol.objects.all()
    if exchange_code:
        symbols = symbols.filter(exchange__code=exchange_code)

    # Count by signal
    signal_counts = {}
    for signal in ['STRONG_BUY', 'BUY', 'HOLD', 'SELL', 'STRONG_SELL', 'NA']:
        signal_counts[signal] = symbols.filter(obv_status=signal).count()

    total = symbols.count()

    # Build summary
    summary_parts = []
    if exchange_code:
        summary_parts.append(f"Market Overview for {exchange_code}")
    else:
        summary_parts.append("Overall Market Overview")

    summary_parts.append(f"Total Symbols: {total}")
    summary_parts.append(
        f"Buy Signals: {signal_counts['STRONG_BUY'] + signal_counts['BUY']} "
        f"({(signal_counts['STRONG_BUY'] + signal_counts['BUY']) / total * 100:.1f}%)"
    )
    summary_parts.append(
        f"Sell Signals: {signal_counts['STRONG_SELL'] + signal_counts['SELL']} "
        f"({(signal_counts['STRONG_SELL'] + signal_counts['SELL']) / total * 100:.1f}%)"
    )

    summary = ". ".join(summary_parts) + "."

    return {
        "summary": summary,
        "exchange": exchange_code,
        "total_symbols": total,
        "signal_distribution": signal_counts,
        "bullish_percentage": (signal_counts['STRONG_BUY'] + signal_counts['BUY']) / total * 100 if total > 0 else 0,
        "bearish_percentage": (signal_counts['STRONG_SELL'] + signal_counts['SELL']) / total * 100 if total > 0 else 0
    }


def build_system_prompt():
    """
    Build a system prompt for the LLM that explains the context and available data.

    Returns:
        str: System prompt
    """
    return """You are ZimuaBull AI, a financial analysis assistant with access to real-time stock market data and portfolio information.

Your capabilities:
- Analyze stock symbols with technical indicators (OBV, trend angles, predictions)
- Provide portfolio performance analysis and recommendations
- Explain trading signals (STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL, NA)
- Compare stocks and identify opportunities
- Track daily predictions and historical accuracy

Trading Signal Meanings:
- STRONG_BUY: All bullish indicators align (positive prediction, strong volume, uptrend, high accuracy)
- BUY: Multiple bullish signals present
- HOLD: Mixed signals or sideways movement
- SELL: Multiple bearish signals present
- STRONG_SELL: All bearish indicators align (negative prediction, weak volume, downtrend, high accuracy)
- NA: Insufficient data or unreliable predictions

Key Indicators:
- OBV Signal Sum: Measures buying/selling pressure over last 3 days (-3 to +3)
- 30-Day Trend: Trendline angle in degrees (positive = uptrend, negative = downtrend)
- Prediction: AI forecast for next 5 days (POSITIVE/NEGATIVE/NEUTRAL)
- Accuracy: Historical prediction accuracy (0.0 to 1.0)

Important: You provide analysis and insights, not financial advice. Always remind users to do their own research and consult financial advisors for investment decisions."""


def format_conversation_context(user, query, **kwargs):
    """
    Build full context for LLM including user data, query, and relevant information.

    Args:
        user: Django User instance
        query: User's question/message
        **kwargs: Additional context (portfolio_ids, symbol, exchange, etc.)

    Returns:
        dict: Full context for LLM
    """
    context = {
        "system_prompt": build_system_prompt(),
        "user_query": query,
        "timestamp": datetime.now().isoformat(),
        "user_context": {}
    }

    # Add user's portfolios if requested
    if 'portfolio_ids' in kwargs:
        portfolios = Portfolio.objects.filter(
            user=user,
            id__in=kwargs['portfolio_ids']
        )
        context['user_context']['portfolios'] = [
            format_portfolio_for_llm(p) for p in portfolios
        ]

    # Add specific symbol if requested
    if 'symbol' in kwargs and 'exchange' in kwargs:
        try:
            symbol = Symbol.objects.get(
                symbol=kwargs['symbol'],
                exchange__code=kwargs['exchange']
            )
            context['user_context']['symbol'] = format_symbol_for_llm(symbol)
        except Symbol.DoesNotExist:
            pass

    # Add market overview if requested
    if kwargs.get('include_market_overview'):
        context['user_context']['market_overview'] = format_market_overview_for_llm(
            kwargs.get('exchange')
        )

    return context
