import logging
from celery import shared_task
from zimuabull.models import Symbol, DaySymbol
from zimuabull.scanners.tse import BaseScanner
import pandas as pd

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True, queue="pidashtasks")
def recalculate_predictions_for_symbol(symbol_id):
    """
    Recalculate predictions for a single symbol using existing DaySymbol data
    """
    try:
        symbol = Symbol.objects.get(id=symbol_id)
        logger.info(f"Recalculating predictions for {symbol.symbol}")

        # Get all existing day symbol data for this symbol
        day_symbols = DaySymbol.objects.filter(symbol=symbol).order_by('date')

        if not day_symbols.exists():
            logger.warning(f"No historical data found for {symbol.symbol}")
            return f"No data for {symbol.symbol}"

        # Convert to DataFrame format that calculate_predictions expects
        data = {
            'date': [],
            'open': [],
            'high': [],
            'low': [],
            'adj_close': [],
            'close': [],
            'volume': [],
            'obv': [],
            'obv_signal': [],
            'obv_signal_sum': [],
            'price_diff': [],
            '30_day_price_diff_avg': [],
            '30_day_close_trendline': [],
            'status': []
        }

        for ds in day_symbols:
            data['date'].append(ds.date)
            data['open'].append(ds.open)
            data['high'].append(ds.high)
            data['low'].append(ds.low)
            data['adj_close'].append(ds.adj_close)
            data['close'].append(ds.close)
            data['volume'].append(ds.volume)
            data['obv'].append(ds.obv)
            data['obv_signal'].append(ds.obv_signal)
            data['obv_signal_sum'].append(ds.obv_signal_sum)
            data['price_diff'].append(ds.price_diff)
            data['30_day_price_diff_avg'].append(ds.thirty_price_diff)
            data['30_day_close_trendline'].append(ds.thirty_close_trend)
            data['status'].append(ds.status)

        res = pd.DataFrame(data)

        # Use the scanner's calculate_predictions method
        scanner = BaseScanner(symbol.exchange)
        scanner.calculate_predictions(symbol, res)

        logger.info(f"Successfully recalculated predictions for {symbol.symbol}")
        return f"Recalculated predictions for {symbol.symbol}"

    except Symbol.DoesNotExist:
        logger.error(f"Symbol with id {symbol_id} not found")
        return "Symbol not found"
    except Exception as e:
        logger.error(f"Error recalculating predictions for symbol {symbol_id}: {e}")
        return f"Error: {e}"


@shared_task(ignore_result=True, queue="pidashtasks")
def recalculate_all_predictions():
    """
    Recalculate predictions for all symbols in the database
    """
    symbols = Symbol.objects.all()
    total_symbols = symbols.count()

    logger.info(f"Starting recalculation of predictions for {total_symbols} symbols")

    dispatched_count = 0
    for symbol in symbols:
        try:
            recalculate_predictions_for_symbol.delay(symbol.id)
            dispatched_count += 1
            logger.info(f"Dispatched recalculation for {symbol.symbol} ({dispatched_count}/{total_symbols})")
        except Exception as e:
            logger.error(f"Error dispatching recalculation for {symbol.symbol}: {e}")

    logger.info(f"Dispatched {dispatched_count} recalculation tasks")
    return f"Dispatched {dispatched_count} recalculation tasks"
