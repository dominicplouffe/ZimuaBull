import datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

import pytz
import yfinance as yf
from celery import shared_task

from zimuabull.models import Portfolio, PortfolioHolding, PortfolioTransaction, PortfolioHoldingLog


def resolve_tsx_ticker(symbol, exchange_code):
    """
    Specialized function for resolving Toronto Stock Exchange (TSX) tickers

    Handles different ticker variations for Canadian stocks
    """
    # If exchange is TSX or TO, always append .TO
    if exchange_code in ["TSE", "TO"]:
        return f"{symbol}.TO"

    return symbol  # For other exchanges, return as-is

def safe_decimal_convert(value):
    """
    Safely convert value to Decimal, handling various input types

    Args:
        value: Input value to convert to Decimal

    Returns:
        Decimal representation or 0 if conversion fails
    """
    if value is None:
        return Decimal("0")

    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        return Decimal("0")

@shared_task
def update_portfolio_symbols_prices():
    """
    Fetch latest prices for all symbols in user portfolios
    and update their current market value

    Adjusts retrieval frequency based on market hours
    """
    # Get all unique symbols from portfolio holdings
    portfolios = Portfolio.objects.all()

    # Track exchanges to avoid redundant market checks
    checked_exchanges = {}

    # Track overall results
    successful_updates = []
    failed_updates = []

    for portfolio in portfolios:
        holdings = PortfolioHolding.objects.filter(portfolio=portfolio)

        for holding in holdings:
            symbol = holding.symbol
            exchange = symbol.exchange

            # Check market status only once per exchange
            if exchange.code not in checked_exchanges:
                checked_exchanges[exchange.code] = is_market_open(exchange.code)

            checked_exchanges[exchange.code]

            try:
                # Resolve ticker with special handling for TSX
                full_ticker = resolve_tsx_ticker(symbol.symbol, exchange.code)

                # Fetch price
                ticker = yf.Ticker(full_ticker)

                # Get price using different methods
                try:
                    latest_price = ticker.info.get("regularMarketPrice")
                except Exception:
                    # Fallback to history method if info fails
                    latest_history = ticker.history(period="1d")
                    latest_price = latest_history["Close"].iloc[-1] if not latest_history.empty else None

                # Validate and convert price and quantity
                if latest_price is not None:
                    # Ensure price and quantity are converted to Decimal safely
                    latest_price_decimal = safe_decimal_convert(latest_price)
                    quantity = safe_decimal_convert(holding.quantity)

                    # Update holding with latest price and symbol's latest price
                    with transaction.atomic():
                        holding.current_price = latest_price_decimal
                        holding.total_value = latest_price_decimal * quantity
                        holding.save()

                        # Update the symbol's latest price
                        symbol.latest_price = latest_price_decimal
                        symbol.price_updated_at = timezone.now()
                        symbol.save(update_fields=["latest_price", "price_updated_at"])

                    successful_updates.append(f"{symbol.symbol} ({exchange.code}): ${latest_price_decimal}")
                else:
                    failed_updates.append(f"{symbol.symbol} ({exchange.code}): No price data")

            except Exception as e:
                # Log the error, but continue processing other symbols
                error_msg = f"Error updating price for {symbol.symbol} ({exchange.code}): {e}"
                failed_updates.append(error_msg)

    # Generate summary report
    return {
        "total_portfolios": len(portfolios),
        "market_status": checked_exchanges,
        "successful_updates": successful_updates,
        "failed_updates": failed_updates
    }



def update_market_indices():
    """
    Update market indices data (S&P 500, NASDAQ, TSX, etc.)
    Returns summary of updates
    """
    from zimuabull.models import MarketIndex, MarketIndexData

    indices_updated = []
    indices_failed = []

    try:
        indices = MarketIndex.objects.all()
        today = datetime.datetime.now().date()

        for index in indices:
            try:
                ticker = yf.Ticker(index.symbol)

                # Try to get current price first
                try:
                    current_price = ticker.info.get("regularMarketPrice")
                    if not current_price:
                        current_price = ticker.info.get("currentPrice")
                except Exception:
                    current_price = None

                # Fallback to history
                if not current_price:
                    hist = ticker.history(period="1d")
                    if not hist.empty:
                        current_price = hist["Close"].iloc[-1]

                if current_price:
                    # Update or create today's record
                    hist = ticker.history(period="1d")
                    if not hist.empty:
                        row = hist.iloc[-1]
                        MarketIndexData.objects.update_or_create(
                            index=index,
                            date=today,
                            defaults={
                                "open": float(row["Open"]),
                                "high": float(row["High"]),
                                "low": float(row["Low"]),
                                "close": float(row["Close"]),
                                "volume": int(row["Volume"]) if row["Volume"] > 0 else None,
                            }
                        )
                        indices_updated.append(f"{index.symbol}: ${current_price:.2f}")
                    else:
                        indices_failed.append(f"{index.symbol}: No history data")
                else:
                    indices_failed.append(f"{index.symbol}: No price available")

            except Exception as e:
                indices_failed.append(f"{index.symbol}: {e!s}")

    except Exception as e:
        indices_failed.append(f"General error: {e!s}")

    return {
        "updated": indices_updated,
        "failed": indices_failed
    }


def cleanup_orphaned_holdings():
    """
    Clean up holdings that have been fully sold but still exist in the database.

    This function checks for holdings where:
    1. A holding exists (status=ACTIVE)
    2. The symbol has a SELL transaction within the last hour
    3. The holding should have been deleted but wasn't

    For each orphaned holding found:
    - Creates a SELL_CORRECTION log entry
    - Deletes the holding
    - Returns summary of corrections made

    Returns:
        dict: Summary of cleaned holdings and any errors
    """
    from datetime import timedelta

    cleaned_holdings = []
    errors = []

    try:
        # Get all active holdings
        active_holdings = PortfolioHolding.objects.filter(status='ACTIVE')

        for holding in active_holdings:
            try:
                # Check for recent SELL transactions for this holding
                one_hour_ago = timezone.now() - timedelta(hours=1)

                recent_sells = PortfolioTransaction.objects.filter(
                    portfolio=holding.portfolio,
                    symbol=holding.symbol,
                    transaction_type='SELL',
                    created_at__gte=one_hour_ago
                ).order_by('-created_at')

                if recent_sells.exists():
                    # Calculate total sells vs current holding quantity
                    total_sold = sum(txn.quantity for txn in recent_sells)

                    # If holding quantity is 0 or less, or very small (rounding errors)
                    if holding.quantity <= Decimal('0.0001'):
                        # This holding should have been deleted
                        # Create a SELL_CORRECTION log entry
                        PortfolioHoldingLog.objects.create(
                            portfolio=holding.portfolio,
                            symbol=holding.symbol,
                            transaction=recent_sells.first(),  # Link to most recent sell
                            operation='SELL_CORRECTION',
                            quantity_before=holding.quantity,
                            average_cost_before=holding.average_cost,
                            quantity_after=Decimal('0'),
                            average_cost_after=None,
                            transaction_type='SELL',
                            transaction_quantity=holding.quantity,
                            transaction_price=holding.average_cost,
                            transaction_date=recent_sells.first().transaction_date,
                            holding_status='CORRECTED',
                            notes=f"CORRECTION: Orphaned holding detected and removed. "
                                  f"Holding had {holding.quantity} shares after SELL transaction(s) totaling {total_sold} shares. "
                                  f"This should have been deleted during the original transaction. Auto-corrected by cleanup task."
                        )

                        # Delete the holding
                        holding_info = f"{holding.portfolio.name} - {holding.symbol.symbol}: {holding.quantity} shares"
                        holding.delete()

                        cleaned_holdings.append(holding_info)

            except Exception as e:
                error_msg = f"Error processing holding {holding.id} ({holding.symbol.symbol}): {str(e)}"
                errors.append(error_msg)

    except Exception as e:
        errors.append(f"General cleanup error: {str(e)}")

    return {
        "cleaned_count": len(cleaned_holdings),
        "cleaned_holdings": cleaned_holdings,
        "errors": errors
    }


@shared_task
def market_pulse_update():
    """
    Combined pulse task that updates both portfolio symbols and market indices.
    Runs every 5 minutes during trading hours.

    This task:
    1. Updates all portfolio symbol prices
    2. Updates market indices (S&P 500, NASDAQ, TSX, etc.)
    3. Cleans up orphaned holdings (holdings that should have been deleted)
    4. Only runs during market hours for efficiency

    Returns comprehensive summary of all updates.
    """
    # Check if any major market is open
    major_exchanges = ["TSE", "NASDAQ", "NYSE"]
    any_market_open = False
    market_status = {}

    for exchange_code in major_exchanges:
        is_open = is_market_open(exchange_code)
        market_status[exchange_code] = is_open
        if is_open:
            any_market_open = True

    # If no markets are open, skip the update
    if not any_market_open:
        return {
            "status": "skipped",
            "reason": "All markets closed",
            "market_status": market_status,
            "timestamp": timezone.now().isoformat()
        }

    # Run all updates
    portfolio_report = update_portfolio_symbols_prices()
    indices_report = update_market_indices()
    cleanup_report = cleanup_orphaned_holdings()

    # Combine reports
    return {
        "status": "completed",
        "timestamp": timezone.now().isoformat(),
        "market_status": market_status,
        "portfolio_updates": {
            "successful": len(portfolio_report.get("successful_updates", [])),
            "failed": len(portfolio_report.get("failed_updates", [])),
            "details": portfolio_report
        },
        "index_updates": {
            "successful": len(indices_report.get("updated", [])),
            "failed": len(indices_report.get("failed", [])),
            "details": indices_report
        },
        "holding_cleanup": {
            "cleaned": cleanup_report.get("cleaned_count", 0),
            "errors": len(cleanup_report.get("errors", [])),
            "details": cleanup_report
        }
    }


def is_market_open(exchange_code):
    """
    Check if the market is currently open for a given exchange

    Supports major exchanges:
    - TO/TSE: Toronto Stock Exchange
    - NYSE: New York Stock Exchange
    - NASDAQ: NASDAQ
    """
    # Mapping of exchange codes to market indices and timezones
    exchange_market_map = {
        "TO": {
            "index": "^GSPTSE",    # S&P/TSX Composite index for Toronto Stock Exchange
            "timezone": "America/Toronto",
        },
        "TSE": {
            "index": "^GSPTSE",    # Alternate code for Toronto Stock Exchange
            "timezone": "America/Toronto",
        },
        "NYSE": {
            "index": "^NYA",       # NYSE Composite index
            "timezone": "America/New_York",
        },
        "NASDAQ": {
            "index": "^IXIC",      # NASDAQ Composite index
            "timezone": "America/New_York",
        }
    }

    try:
        # Get the current time in the exchange's timezone
        now = timezone.now()

        # Define market hours (assuming standard market hours)
        market_open_time = datetime.time(9, 30)  # 9:30 AM
        market_close_time = datetime.time(16, 0)  # 4:00 PM

        # If exchange is not in our map, default to UTC
        exchange_info = exchange_market_map.get(exchange_code, {
            "timezone": "UTC"
        })

        # Localize the current time to the exchange's timezone
        tz = pytz.timezone(exchange_info["timezone"])
        local_now = now.astimezone(tz)
        current_time = local_now.time()
        current_weekday = local_now.weekday()

        # Check if it's a weekday (Monday = 0, Friday = 4)
        is_weekday = 0 <= current_weekday <= 4

        # Check if current time is within market hours
        return (
            is_weekday and
            market_open_time <= current_time <= market_close_time
        )


    except Exception:
        # Log the error, default to assuming market is closed
        return False
