from datetime import datetime, timedelta, timezone
import logging

from zimuabull.constants import EXCHANGES
from zimuabull.models import (
    Symbol,
    Exchange,
    CloseBucketChoice,
    DayPrediction,
    DayPredictionChoice,
)

import pandas as pd
import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)


class BaseScanner:
    def __init__(self, exchange):
        self.exchange = exchange
        self.res = None
        self.suffix = EXCHANGES[exchange.code].get("suffix", None)

    def most_recent_trading_day(self):
        dt = datetime.now(tz=timezone.utc).date()

        # If today is a weekend, then we need to go back to the most recent Friday
        if dt.weekday() == 5:
            dt = dt - timedelta(days=1)
        elif dt.weekday() == 6:
            dt = dt - timedelta(days=2)

        return dt

    def request_data(self, symbol):
        if self.suffix:
            symbol = f"{symbol}{self.suffix}"
        t = yf.Ticker(symbol)
        return t.history(period="1y")

    def get_obv_data(self, symbol):
        df = self.request_data(symbol)

        data = {
            "date": [],
            "open": [],
            "high": [],
            "low": [],
            "adj_close": [],
            "close": [],
            "volume": [],
            "obv": [],
            "obv_signal": [],
            "obv_signal_sum": [],
            "price_diff": [],
        }
        obv = 0
        prev_close = 0
        rows = df.reset_index().to_dict("records")
        i = 0
        for row in rows:
            try:
                dt = row["Date"].date()
                open = float(row["Open"])
                high = float(row["High"])
                low = float(row["Low"])
                close = float(row["Close"])
                volume = int(row["Volume"])

                if dt < datetime.now(tz=timezone.utc).date() - timedelta(days=365):
                    continue

                data["date"].append(dt)
                data["open"].append(open)
                data["high"].append(high)
                data["low"].append(low)
                data["adj_close"].append(0.00)
                data["close"].append(close)
                data["volume"].append(volume)
                if prev_close < close:
                    obv += volume
                elif prev_close > close:
                    obv -= volume
                data["obv"].append(obv)
                prev_close = close

                if i == 0:
                    data["obv_signal"].append(0)
                else:
                    if data["obv"][i - 1] < data["obv"][i]:
                        data["obv_signal"].append(1)
                    else:
                        data["obv_signal"].append(0)
                if i < 3:
                    data["obv_signal_sum"].append(0)
                else:
                    data["obv_signal_sum"].append(sum(data["obv_signal"][i - 3 : i]))

                if i == 0:
                    data["price_diff"].append(0)
                else:
                    data["price_diff"].append(abs(close - data["close"][i - 1]))
            except ValueError as e:
                logger.error(f"Error processing {row['Date']}: {e}")
                return None

            i += 1

        res = pd.DataFrame(data)
        res["30_day_price_diff_avg"] = res["price_diff"].rolling(window=30).mean()
        res["30_day_close_trendline"] = (
            res["close"].rolling(window=30).apply(self.calc_slope_angle)
        )
        res.fillna(0, inplace=True)
        return res

    def calc_slope_angle(self, x):
        N = len(x)
        if N == 0:
            return np.nan
        # Assuming the 'day' index is a simple numerical index starting from 0 or 1
        # Modify if your DataFrame index is different (e.g., dates)
        days = np.arange(N)
        sum_x = np.sum(days)
        sum_y = np.sum(x)
        sum_xy = np.sum(days * x)
        sum_x2 = np.sum(days**2)
        denominator = N * sum_x2 - sum_x**2

        # Avoid division by zero
        if denominator == 0:
            return np.nan
        slope = (N * sum_xy - sum_x * sum_y) / denominator

        # Calculate angle in degrees
        angle = np.degrees(np.arctan(slope))
        return angle

    def get_close_bucket(self, res):
        # get the last value of the 30_day_close_trendline from res
        close_trend_line = res["30_day_close_trendline"].iloc[-1]

        if close_trend_line >= 5:
            return CloseBucketChoice.UP
        elif close_trend_line <= -5:
            return CloseBucketChoice.DOWN
        return CloseBucketChoice.NA

    def calculate_predictions(self, symbol, res):
        """
        Predict near-future stock movement using technical indicators.
        Uses a combination of:
        - Price momentum (rate of change)
        - Trend strength (30-day trendline angle)
        - Volume momentum (OBV signal)
        - Volatility (price differential trends)
        """
        # Need at least 30 days for meaningful predictions
        if len(res) < 30:
            logger.warning(f"Insufficient data for predictions on {symbol.symbol}")
            return

        # Calculate additional features for prediction
        res['price_momentum'] = res['close'].pct_change(periods=5) * 100  # 5-day % change
        res['volume_trend'] = res['obv_signal'].rolling(window=5).mean()  # 5-day avg OBV signal
        res['volatility'] = res['price_diff'].rolling(window=10).std()  # 10-day volatility

        positive_count = 0
        total_count = 0

        # Start predictions after we have enough historical data
        for i in range(30, len(res)):
            row = res.iloc[i]

            # Get current values
            price_momentum = row['price_momentum']
            trend_angle = row['30_day_close_trendline']
            volume_trend = row['volume_trend']
            volatility = row['volatility']
            obv_signal_sum = row['obv_signal_sum']

            # Initialize score
            score = 0

            # Scoring system (-3 to +3)
            # 1. Price Momentum (strong momentum = likely continuation)
            if price_momentum > 3:
                score += 1
            elif price_momentum < -3:
                score -= 1

            # 2. Trend Strength (strong uptrend/downtrend)
            if trend_angle > 5:
                score += 1
            elif trend_angle < -5:
                score -= 1

            # 3. Volume Momentum (buying/selling pressure)
            if volume_trend > 0.7:  # Strong buying
                score += 1
            elif volume_trend < 0.3:  # Strong selling
                score -= 1

            # 4. OBV Signal (additional confirmation)
            if obv_signal_sum >= 2:  # Consecutive volume increases
                score += 0.5
            elif obv_signal_sum == 0:  # Consecutive volume decreases
                score -= 0.5

            # 5. Volatility adjustment (high volatility = less confidence in trend)
            # Reduce score magnitude when volatility is high (less predictable)
            if volatility > 0:
                avg_volatility = res['volatility'].mean()
                if volatility > 1.5 * avg_volatility:  # High volatility
                    score *= 0.7  # Dampen the score
                elif volatility < 0.5 * avg_volatility:  # Low volatility
                    score *= 1.2  # Amplify the score (more confidence)

            # Determine prediction based on score
            if score >= 1.5:
                prediction = DayPredictionChoice.POSITIVE
            elif score <= -1.5:
                prediction = DayPredictionChoice.NEGATIVE
            else:
                prediction = DayPredictionChoice.NEUTRAL

            # For accuracy calculation, look ahead 5 days to see if prediction was correct
            future_price = None
            actual_movement = None
            if i + 5 < len(res):
                current_close = row['close']
                future_close = res.iloc[i + 5]['close']
                price_change_pct = ((future_close - current_close) / current_close) * 100

                # Determine actual movement (2% threshold for significant movement)
                if price_change_pct > 2:
                    actual_movement = DayPredictionChoice.POSITIVE
                elif price_change_pct < -2:
                    actual_movement = DayPredictionChoice.NEGATIVE
                else:
                    actual_movement = DayPredictionChoice.NEUTRAL

                future_price = future_close

                # Count accuracy
                total_count += 1
                if prediction == actual_movement:
                    positive_count += 1

            # Store prediction
            DayPrediction.objects.update_or_create(
                symbol=symbol,
                date=row['date'],
                defaults=dict(
                    buy_price=row['close'],
                    sell_price=future_price if future_price else row['close'],
                    diff=future_price - row['close'] if future_price else 0,
                    prediction=prediction,
                    buy_date=row['date'],
                    sell_date=res.iloc[i + 5]['date'] if i + 5 < len(res) else None,
                ),
            )

        # Update symbol accuracy based on prediction accuracy
        symbol.accuracy = positive_count / total_count if total_count > 0 else 0
        symbol.save()

        logger.info(f"Predictions for {symbol.symbol}: {positive_count}/{total_count} accurate ({symbol.accuracy:.2%})")

    def scan(self):
        """
        Scan all symbols for this exchange using Celery tasks for parallel processing.
        Use CELERY_TASK_ALWAYS_EAGER=True in settings to run synchronously for testing.
        """
        from zimuabull.tasks.process_symbol import process_symbol_data

        symbols = Symbol.objects.filter(exchange=self.exchange)
        total_symbols = symbols.count()

        logger.info(f"Starting scan for {self.exchange.code} with {total_symbols} symbols")

        dispatched_count = 0
        for symbol in symbols:
            try:
                # Dispatch Celery task for each symbol
                # Will run async if CELERY_TASK_ALWAYS_EAGER=False (production)
                # Will run sync if CELERY_TASK_ALWAYS_EAGER=True (testing/development)
                process_symbol_data.delay(symbol.id, self.exchange.code)
                dispatched_count += 1
                logger.info(f"Dispatched task for {symbol.symbol} ({dispatched_count}/{total_symbols})")
            except Exception as e:
                logger.error(f"Error dispatching task for {symbol.symbol}: {e}")

        logger.info(f"Dispatched {dispatched_count} Celery tasks for {self.exchange.code}")


class TSEScanner(BaseScanner):
    def __init__(self):
        exchange = Exchange.objects.get(code="TSE")
        super().__init__(exchange)


class NASDAQScanner(BaseScanner):
    def __init__(self):
        exchange = Exchange.objects.get(code="NASDAQ")
        super().__init__(exchange)


class NYSEScanner(BaseScanner):
    def __init__(self):
        exchange = Exchange.objects.get(code="NYSE")
        super().__init__(exchange)
