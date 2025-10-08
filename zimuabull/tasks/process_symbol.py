import logging
from celery import shared_task
from zimuabull.models import Symbol, DaySymbol, DaySymbolChoice, SignalHistory, DayPrediction
from zimuabull.scanners.tse import BaseScanner

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True, queue="pidashtasks")
def process_symbol_data(symbol_id, exchange_code):
    """
    Process a single symbol's data using the appropriate scanner
    """
    try:
        # Get the symbol
        symbol = Symbol.objects.get(id=symbol_id)
        logger.info(f"Processing symbol: {symbol.symbol} ({exchange_code})")

        # Check if we already have recent data to avoid unnecessary processing
        scanner = BaseScanner(symbol.exchange)
        recent_data = DaySymbol.objects.filter(
            symbol=symbol,
            date=scanner.most_recent_trading_day()
        ).first()

        if recent_data is not None:
            logger.info(f"Skipping {symbol.symbol} - already has recent data")
            return f"Skipped {symbol.symbol} - already up to date"

        # Process the symbol
        logger.info(f"Scanning {symbol.symbol}")

        # Get OBV data
        res = scanner.get_obv_data(symbol.symbol)
        if res is None:
            logger.error(f"No data retrieved for {symbol.symbol}")
            return f"No data for {symbol.symbol}"

        # Process the data
        statuses = []

        for _, row in res.iterrows():
            try:
                status = DaySymbolChoice.NA

                DaySymbol.objects.update_or_create(
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
                statuses.append(status)

            except Exception as e:
                logger.error(f"Error processing row for {symbol.symbol}: {e}")
                continue

        # Update symbol metadata
        if len(res) > 0:
            res["status"] = statuses
            last_row = res.iloc[-1]
            symbol.last_open = last_row["open"]
            symbol.last_close = last_row["close"]
            symbol.last_volume = last_row["volume"]
            symbol.thirty_close_trend = last_row["30_day_close_trendline"]
            symbol.close_bucket = scanner.get_close_bucket(res)
            symbol.save()

            # Calculate predictions
            scanner.calculate_predictions(symbol, res)

            # Calculate and update trading signal based on latest data
            try:
                previous_signal = symbol.obv_status
                new_signal = symbol.update_trading_signal()

                # Track signal changes in history
                if new_signal != previous_signal:
                    latest_prediction = DayPrediction.objects.filter(symbol=symbol).order_by('-date').first()

                    SignalHistory.objects.create(
                        symbol=symbol,
                        date=last_row["date"],
                        previous_signal=previous_signal,
                        new_signal=new_signal,
                        price=last_row["close"],
                        volume=last_row["volume"],
                        prediction=latest_prediction.prediction if latest_prediction else None,
                        reason=f"Signal changed from {previous_signal} to {new_signal} during daily processing"
                    )
                    logger.info(f"Signal change recorded for {symbol.symbol}: {previous_signal} -> {new_signal}")

                logger.info(f"Updated trading signal for {symbol.symbol}: {new_signal}")
            except Exception as e:
                logger.warning(f"Failed to calculate trading signal for {symbol.symbol}: {e}")

        logger.info(f"Successfully processed {symbol.symbol}")
        return f"Processed {symbol.symbol} successfully"

    except Symbol.DoesNotExist:
        logger.error(f"Symbol with id {symbol_id} not found")
        return f"Symbol with id {symbol_id} not found"
    except Exception as e:
        logger.error(f"Error processing symbol {symbol_id}: {e}")
        return f"Error processing symbol {symbol_id}: {e}"