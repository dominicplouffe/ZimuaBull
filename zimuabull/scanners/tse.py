from datetime import datetime, timedelta
import logging

from zimuabull.constants import EXCHANGES
from zimuabull.models import Symbol, Exchange, DaySymbol, DaySymbolChoice

import pandas as pd
import numpy as np

from urllib.error import HTTPError

logger = logging.getLogger(__name__)


class BaseScanner:
    def __init__(self, exchange):
        self.exchange = exchange
        self.symbol_url = EXCHANGES[exchange.code]["symbol_url"]

    def scan(self):
        raise NotImplementedError()

    def get_obv_data(self, url):
        df = pd.read_csv(url)

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
        rows = df.to_dict("records")
        for i, row in enumerate(rows):
            try:
                data["date"].append(datetime.strptime(row["Date"], "%Y-%m-%d"))
                data["open"].append(float(row["Open"]))
                data["high"].append(float(row["High"]))
                data["low"].append(float(row["Low"]))
                data["adj_close"].append(float(row["Adj Close"]))
                data["close"].append(float(row["Close"]))
                data["volume"].append(int(row["Volume"]))
                if prev_close < float(row["Close"]):
                    obv += int(row["Volume"])
                elif prev_close > float(row["Close"]):
                    obv -= int(row["Volume"])
                data["obv"].append(obv)
                prev_close = float(row["Close"])

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
                    data["price_diff"].append(
                        abs(float(row["Close"]) - data["close"][i - 1])
                    )
            except ValueError as e:
                logger.error(f"Error processing {row['Date']}: {e}")
                return None

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


class TSEScanner(BaseScanner):
    def __init__(self):
        exchange = Exchange.objects.get(code="TSE")
        super().__init__(exchange)

    def scan(self):

        start_date = datetime.today() - timedelta(days=365)
        start_date = datetime(start_date.year, start_date.month, start_date.day)
        end_date = datetime.now()
        end_date = datetime(end_date.year, end_date.month, end_date.day)

        for symbol in Symbol.objects.filter(exchange=self.exchange):

            logger.info(f"Scanning {symbol.symbol} from {start_date} to {end_date}")

            url = self.symbol_url % (
                symbol.symbol,
                int(start_date.timestamp()),
                int(end_date.timestamp()),
            )

            try:
                res = self.get_obv_data(url)
            except HTTPError as e:
                logger.error(f"Error downloading {symbol.symbol}: {e} - {url}")
                continue

            if res is None:
                continue

            prev_status = DaySymbolChoice.NA
            days_since_buy = 0
            for _, row in res.iterrows():
                try:
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
                except ValueError as e:
                    logger.error(f"Error saving {symbol.symbol}: {e}")
                    continue
