"""
Trading Signal Calculation Logic

This module contains the logic for calculating BUY/SELL/HOLD signals
based on technical indicators and predictions.
"""

from .models import DaySymbolChoice, DayPrediction, DaySymbol


def calculate_trading_signal(symbol):
    """
    Calculate trading signal based on latest prediction and technical indicators.

    Args:
        symbol: Symbol model instance

    Returns:
        DaySymbolChoice: The calculated trading signal

    Signal Logic:
        - STRONG_BUY: All bullish indicators align (positive prediction, strong OBV, uptrend, high accuracy)
        - BUY: Multiple bullish signals present
        - HOLD: Mixed/weak signals or sideways movement
        - SELL: Multiple bearish signals present
        - STRONG_SELL: All bearish indicators align (negative prediction, weak OBV, downtrend, high accuracy)
        - NA: Insufficient data or unreliable predictions
    """
    # Get latest prediction
    latest_prediction = DayPrediction.objects.filter(
        symbol=symbol
    ).order_by('-date').first()

    if not latest_prediction:
        return DaySymbolChoice.NA

    # Get latest day symbol data
    latest_day = DaySymbol.objects.filter(
        symbol=symbol
    ).order_by('-date').first()

    if not latest_day:
        return DaySymbolChoice.NA

    # Extract key metrics
    pred = latest_prediction.prediction
    obv_sum = latest_day.obv_signal_sum
    trend = latest_day.thirty_close_trend
    bucket = symbol.close_bucket
    accuracy = symbol.accuracy if symbol.accuracy is not None else 0.5

    # If accuracy is too low, return NA (unreliable predictions)
    if accuracy < 0.40:
        return DaySymbolChoice.NA

    # STRONG_BUY: All bullish indicators align strongly
    if (pred == 'POSITIVE' and
        obv_sum >= 2 and
        trend > 15 and
        bucket == 'UP' and
        accuracy >= 0.70):
        return DaySymbolChoice.STRONG_BUY

    # STRONG_SELL: All bearish indicators align strongly
    if (pred == 'NEGATIVE' and
        obv_sum <= -2 and
        trend < -15 and
        bucket == 'DOWN' and
        accuracy >= 0.70):
        return DaySymbolChoice.STRONG_SELL

    # BUY: Multiple bullish signals present
    if ((pred == 'POSITIVE' and obv_sum >= 1) or
        (pred == 'NEUTRAL' and obv_sum >= 2 and trend > 10) or
        (pred == 'POSITIVE' and trend > 5 and obv_sum >= 0)):
        return DaySymbolChoice.BUY

    # SELL: Multiple bearish signals present
    if ((pred == 'NEGATIVE' and obv_sum <= -1) or
        (pred == 'NEUTRAL' and obv_sum <= -2 and trend < -10) or
        (pred == 'NEGATIVE' and trend < -5 and obv_sum <= 0)):
        return DaySymbolChoice.SELL

    # HOLD: Default for mixed/weak signals
    # This includes:
    # - NEUTRAL predictions with moderate OBV
    # - Conflicting signals (e.g., positive prediction but negative trend)
    # - Sideways movement (trend between -5 and 5)
    return DaySymbolChoice.HOLD


def get_signal_explanation(symbol):
    """
    Get a human-readable explanation of why a symbol has its current signal.

    Args:
        symbol: Symbol model instance

    Returns:
        dict: Contains signal and explanation
    """
    latest_prediction = DayPrediction.objects.filter(
        symbol=symbol
    ).order_by('-date').first()

    if not latest_prediction:
        return {
            'signal': DaySymbolChoice.NA,
            'explanation': 'No prediction data available'
        }

    latest_day = DaySymbol.objects.filter(
        symbol=symbol
    ).order_by('-date').first()

    if not latest_day:
        return {
            'signal': DaySymbolChoice.NA,
            'explanation': 'No daily trading data available'
        }

    pred = latest_prediction.prediction
    obv_sum = latest_day.obv_signal_sum
    trend = latest_day.thirty_close_trend
    bucket = symbol.close_bucket
    accuracy = symbol.accuracy if symbol.accuracy is not None else 0.5

    signal = calculate_trading_signal(symbol)

    # Build explanation
    explanation_parts = []
    explanation_parts.append(f"Prediction: {pred}")
    explanation_parts.append(f"OBV Signal Sum: {obv_sum}")
    explanation_parts.append(f"30-day Trend: {trend:.2f}°")
    explanation_parts.append(f"Price Bucket: {bucket}")
    explanation_parts.append(f"Accuracy: {accuracy:.1%}")

    return {
        'signal': signal,
        'prediction': pred,
        'obv_signal_sum': obv_sum,
        'trend_angle': round(trend, 2),
        'price_bucket': bucket,
        'accuracy': round(accuracy, 3),
        'explanation': ' | '.join(explanation_parts)
    }
