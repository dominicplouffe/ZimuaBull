from datetime import datetime, timedelta, timezone
import logging

from zimuabull.constants import EXCHANGES
from zimuabull.models import (
    Symbol,
    Exchange,
    DaySymbol,
    DaySymbolChoice,
    CloseBucketChoice,
    DayPrediction,
    DayPredictionChoice,
)

import pandas as pd
import numpy as np
import requests

from urllib.error import HTTPError
import yfinance as yf

logger = logging.getLogger(__name__)


class BaseScanner:
    def __init__(self, exchange):
        self.exchange = exchange
        self.res = None
        self.suffix = EXCHANGES[exchange.code].get("suffix", None)

    def scan(self):
        raise NotImplementedError()

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

        # Loop through the rows of the dataframe
        buy_price = 0
        buy_date = None
        sell_price = 0
        positive_count = 0
        total_count = 0
        for _, row in res.iterrows():
            status = row["status"]

            if status == DaySymbolChoice.BUY:
                buy_price = row["close"]
                buy_date = row["date"]
            elif status == DaySymbolChoice.SELL:
                sell_price = row["close"]
                if buy_price != 0:
                    diff = sell_price - buy_price
                    total_count += 1
                    prediction = DayPredictionChoice.NEUTRAL
                    if diff > 0:
                        prediction = DayPredictionChoice.POSITIVE
                        positive_count += 1
                    elif diff < 0:
                        prediction = DayPredictionChoice.NEGATIVE

                    DayPrediction.objects.update_or_create(
                        symbol=symbol,
                        date=row["date"],
                        defaults=dict(
                            buy_price=buy_price,
                            sell_price=sell_price,
                            diff=diff,
                            prediction=prediction,
                            buy_date=buy_date,
                            sell_date=row["date"],
                        ),
                    )
                buy_price = 0
                sell_price = 0
        symbol.accuracy = positive_count / total_count if total_count > 0 else 0
        symbol.save()

    def scan(self):
        for symbol in Symbol.objects.filter(exchange=self.exchange):

            DaySymbol.objects.filter(symbol=symbol).delete()
            DayPrediction.objects.filter(symbol=symbol).delete()

            # Check if the symbol is already in the database
            # ds = DaySymbol.objects.filter(
            #     symbol=symbol, date=self.most_recent_trading_day()
            # ).first()

            # if ds is not None:
            #     logger.info(f"Skipping {symbol.symbol}")
            #     continue

            logger.info(f"Scanning {symbol.symbol}")
            try:
                res = self.get_obv_data(symbol.symbol)
            except HTTPError as e:
                logger.error(f"Error downloading {symbol.symbol}: {e} - {url}")
                continue

            if res is None:
                continue

            prev_status = DaySymbolChoice.NA
            days_since_buy = 0
            last_status = DaySymbolChoice.NA
            statuses = []
            for _, row in res.iterrows():
                try:
                    last_status = prev_status
                    status = DaySymbolChoice.NA
                    if prev_status == DaySymbolChoice.BUY:
                        status = DaySymbolChoice.HOLD

                    if (
                        row["obv_signal_sum"] == 0
                        and prev_status == DaySymbolChoice.HOLD
                        and days_since_buy >= 4
                    ):
                        status = DaySymbolChoice.SELL
                    elif (
                        row["obv_signal_sum"] == 0 and prev_status == DaySymbolChoice.NA
                    ):
                        status = DaySymbolChoice.BUY
                        days_since_buy = 0
                    elif (
                        row["obv_signal_sum"] == 2
                        and prev_status == DaySymbolChoice.HOLD
                        and days_since_buy >= 4
                    ):
                        status = DaySymbolChoice.SELL
                    elif prev_status == DaySymbolChoice.HOLD:
                        status = DaySymbolChoice.HOLD
                    day_symbol, _ = DaySymbol.objects.update_or_create(
                        symbol=symbol,
                        date=row["date"],
                        defaults=dict(
                            open=row["open"],
                            high=row["high"],
                            low=row["low"],
                            adj_close=row["adj_close"],
                            close=row["close"],
                            volume=row["volume"],
                            obv=row["obv"],
                            obv_signal=row["obv_signal"],
                            obv_signal_sum=row["obv_signal_sum"],
                            price_diff=row["price_diff"],
                            thirty_price_diff=row["30_day_price_diff_avg"],
                            thirty_close_trend=row["30_day_close_trendline"],
                            status=status,
                        ),
                    )
                    day_symbol.save()
                    prev_status = status
                    days_since_buy += 1
                    statuses.append(status)
                except ValueError as e:
                    logger.error(f"Error saving {symbol.symbol}: {e}")
                    continue

            res["status"] = statuses

            if len(res) == 0:
                continue
            last_row = res.iloc[-1]
            symbol.last_open = last_row["open"]
            symbol.last_close = last_row["close"]
            symbol.last_volume = last_row["volume"]
            symbol.obv_status = last_status
            symbol.thirty_close_trend = last_row["30_day_close_trendline"]
            symbol.close_bucket = self.get_close_bucket(res)
            symbol.save()

            self.calculate_predictions(symbol, res)

            # break


class TSEScanner(BaseScanner):
    def __init__(self):
        exchange = Exchange.objects.get(code="TSE")
        super().__init__(exchange)
