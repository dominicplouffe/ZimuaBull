import logging

from celery import shared_task

from zimuabull.scanners import tse
from zimuabull.scanners.nasdaq import NASDAQScanner
from zimuabull.scanners.nyse import NYSEScanner
from zimuabull.tasks.download_symbols import download_nasdaq, download_nyse, download_tse

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True, queue="pidashtasks")
def scan():
    # Download symbols for all exchanges
    download_tse()
    download_nasdaq()
    download_nyse()

    # Scan TSE
    t = tse.TSEScanner()
    t.scan()

    # Scan NASDAQ
    nasdaq = NASDAQScanner()
    nasdaq.scan()

    # Scan NYSE
    nyse = NYSEScanner()
    nyse.scan()

    # Update technical indicators for recently updated symbols
    logger.info("Calculating technical indicators for recently updated data...")
    try:
        from datetime import datetime, timedelta

        from zimuabull.models import DaySymbol, Symbol

        # Get all symbols that have DaySymbol records in the last 2 days (by date, not updated_at)
        # This ensures we calculate RSI/MACD for all symbols with recent trading data
        recent_date = datetime.now().date() - timedelta(days=2)

        # Find all symbols with DaySymbol records on or after recent_date
        recent_symbols = DaySymbol.objects.filter(
            date__gte=recent_date
        ).values_list("symbol_id", flat=True).distinct()

        symbols = Symbol.objects.filter(id__in=recent_symbols)
        logger.info(f"Found {symbols.count()} symbols with recent trading data (date >= {recent_date})")

        indicators_updated = 0
        for symbol in symbols:
            # Get recent days without RSI/MACD (based on date, not updated_at)
            recent_days = DaySymbol.objects.filter(
                symbol=symbol,
                date__gte=recent_date,
                rsi__isnull=True
            ).order_by("date")

            for day in recent_days:
                # Calculate RSI
                rsi = DaySymbol.calculate_rsi(symbol, day.date, period=14)

                # Calculate MACD
                macd, macd_signal, macd_histogram = DaySymbol.calculate_macd(symbol, day.date)

                # Update if we have values
                updated = False
                if rsi is not None:
                    day.rsi = rsi
                    updated = True

                if macd is not None:
                    day.macd = macd
                    day.macd_signal = macd_signal
                    day.macd_histogram = macd_histogram
                    updated = True

                if updated:
                    day.save(update_fields=["rsi", "macd", "macd_signal", "macd_histogram", "updated_at"])
                    indicators_updated += 1

        logger.info(f"Updated technical indicators for {indicators_updated} records")

    except Exception as e:
        logger.exception(f"Error updating technical indicators: {e}")

    # Update market index data
    logger.info("Updating market index data...")
    try:
        from datetime import datetime, timedelta

        from zimuabull.models import MarketIndex, MarketIndexData

        # Check if yfinance is available
        try:
            import yfinance as yf

            indices = MarketIndex.objects.all()
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)

            indices_updated = 0
            for index in indices:
                # Check if we already have today's data
                if MarketIndexData.objects.filter(index=index, date=today).exists():
                    continue

                try:
                    ticker = yf.Ticker(index.symbol)
                    # Fetch last 2 days to ensure we get latest
                    hist = ticker.history(period="2d")

                    for date, row in hist.iterrows():
                        date_obj = date.date()

                        # Only create if date is yesterday or today
                        if date_obj >= yesterday:
                            MarketIndexData.objects.update_or_create(
                                index=index,
                                date=date_obj,
                                defaults={
                                    "open": float(row["Open"]),
                                    "high": float(row["High"]),
                                    "low": float(row["Low"]),
                                    "close": float(row["Close"]),
                                    "volume": int(row["Volume"]) if row["Volume"] > 0 else None,
                                }
                            )
                            indices_updated += 1

                    logger.info(f"Updated {index.symbol}")

                except Exception as e:
                    logger.warning(f"Error fetching {index.symbol}: {e}")

            logger.info(f"Updated {indices_updated} market index records")

        except ImportError:
            logger.warning("yfinance not installed - skipping market index updates. Install with: pip install yfinance")

    except Exception as e:
        logger.exception(f"Error updating market indices: {e}")
