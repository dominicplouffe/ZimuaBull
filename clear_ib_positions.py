#!/usr/bin/env python
"""
Clear all positions from Interactive Brokers paper trading account.

This script:
1. Connects to IB Gateway/TWS
2. Fetches all current positions
3. Submits SELL market orders for each position
4. Waits for order confirmations

Usage:
    python clear_ib_positions.py --portfolio-id <id>
    python clear_ib_positions.py --portfolio-id 1 --dry-run  # Test without submitting orders
"""

import argparse
import logging
import sys
import time
from decimal import Decimal

import django

# Setup Django
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from zimuabull.daytrading.ib_connector import IBConnector, IBConnectionError, IBOrderError
from zimuabull.models import Portfolio, Symbol

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def get_current_positions(connector: IBConnector):
    """
    Get all current positions from IB.

    Returns:
        List of position objects from IB
    """
    if not connector.is_connected():
        raise IBConnectionError("Not connected to IB")

    # Get positions from IB
    positions = connector.ib.positions()

    if not positions:
        logger.info("No positions found in IB account")
        return []

    logger.info(f"Found {len(positions)} position(s) in IB account:")
    for pos in positions:
        logger.info(f"  - {pos.contract.symbol}: {pos.position} shares @ {pos.avgCost}")

    return positions


def find_or_create_symbol(ib_symbol: str, exchange_code: str, connector: IBConnector) -> Symbol:
    """
    Find or create a Symbol object for the given IB symbol.

    Args:
        ib_symbol: Symbol ticker from IB
        exchange_code: Exchange code (e.g., 'NASDAQ', 'NYSE', 'TSE')
        connector: IB connector instance

    Returns:
        Symbol model instance
    """
    from zimuabull.models import Exchange

    # Try to find the symbol
    # Handle different exchange codes
    if exchange_code == "SMART":
        # SMART routing - try NASDAQ first, then NYSE
        symbol = Symbol.objects.filter(
            symbol=ib_symbol,
            exchange__code__in=["NASDAQ", "NYSE"]
        ).first()
    else:
        symbol = Symbol.objects.filter(
            symbol=ib_symbol,
            exchange__code=exchange_code
        ).first()

    if symbol:
        logger.debug(f"Found existing symbol: {symbol.symbol} on {symbol.exchange.code}")
        return symbol

    # Symbol not found - create a minimal one
    logger.warning(f"Symbol {ib_symbol} not found in database. Creating minimal record.")

    # Get or create exchange
    if exchange_code == "SMART":
        exchange_code = "NASDAQ"  # Default to NASDAQ for SMART routing

    exchange, _ = Exchange.objects.get_or_create(
        code=exchange_code,
        defaults={
            "name": exchange_code,
            "country": "US" if exchange_code in ["NASDAQ", "NYSE"] else "CA"
        }
    )

    # Create minimal symbol
    symbol = Symbol.objects.create(
        symbol=ib_symbol,
        exchange=exchange,
        name=ib_symbol,  # Use symbol as name
        sector="Unknown",
        industry="Unknown"
    )

    logger.info(f"Created new symbol: {symbol.symbol} on {symbol.exchange.code}")
    return symbol


def clear_all_positions(portfolio_id: int, dry_run: bool = False):
    """
    Clear all positions from the IB account.

    Args:
        portfolio_id: Portfolio ID to use for connection
        dry_run: If True, only show what would be done without submitting orders
    """
    # Get portfolio
    try:
        portfolio = Portfolio.objects.get(id=portfolio_id)
    except Portfolio.DoesNotExist:
        logger.error(f"Portfolio {portfolio_id} not found")
        return False

    logger.info(f"Using portfolio: {portfolio.name} (ID: {portfolio.id})")

    # Validate IB configuration
    if not portfolio.use_interactive_brokers:
        logger.error(f"Portfolio {portfolio.id} does not have IB enabled")
        return False

    # Connect to IB
    connector = IBConnector(portfolio)

    try:
        logger.info(f"Connecting to IB at {portfolio.ib_host}:{portfolio.ib_port}...")
        connector.connect()
        logger.info("✓ Connected to IB")

        # Get all positions
        positions = get_current_positions(connector)

        if not positions:
            logger.info("✓ No positions to clear")
            return True

        # Submit SELL orders for each position
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Submitting SELL orders for {len(positions)} position(s)...")
        logger.info(f"{'=' * 80}\n")

        submitted_orders = []

        for pos in positions:
            ib_symbol = pos.contract.symbol
            quantity = abs(pos.position)  # Use absolute value (positive)
            exchange = pos.contract.exchange

            if quantity <= 0:
                logger.warning(f"Skipping {ib_symbol}: quantity is {pos.position}")
                continue

            logger.info(f"Processing {ib_symbol}: {quantity} shares")

            if dry_run:
                logger.info(f"  [DRY RUN] Would submit SELL market order for {quantity} shares of {ib_symbol}")
                continue

            try:
                # Find or create symbol in database
                symbol = find_or_create_symbol(ib_symbol, exchange, connector)

                # Submit SELL market order
                logger.info(f"  Submitting SELL market order for {quantity} shares of {ib_symbol}...")
                trade = connector.submit_market_order(
                    symbol=symbol,
                    action="SELL",
                    quantity=Decimal(str(quantity)),
                    account=portfolio.ib_account
                )

                submitted_orders.append({
                    "symbol": ib_symbol,
                    "quantity": quantity,
                    "trade": trade
                })

                logger.info(f"  ✓ Order submitted (Order ID: {trade.order.orderId})")

                # Small delay between orders
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"  ✗ Failed to submit order for {ib_symbol}: {e}")

        if dry_run:
            logger.info(f"\n{'=' * 80}")
            logger.info("DRY RUN COMPLETE - No orders were actually submitted")
            logger.info(f"{'=' * 80}\n")
            return True

        # Wait for order confirmations
        if submitted_orders:
            logger.info(f"\n{'=' * 80}")
            logger.info(f"Waiting for order confirmations (30 seconds)...")
            logger.info(f"{'=' * 80}\n")

            time.sleep(5)  # Initial wait

            for i in range(5):  # Check 5 times over 25 seconds
                connector.ib.sleep(5)

                logger.info(f"Checking order status... ({(i+1)*5}s)")

                for order_info in submitted_orders:
                    trade = order_info["trade"]
                    status = trade.orderStatus.status
                    filled = trade.orderStatus.filled

                    logger.info(f"  {order_info['symbol']}: {status} ({filled}/{order_info['quantity']} filled)")

            logger.info(f"\n{'=' * 80}")
            logger.info("✓ All orders submitted successfully")
            logger.info(f"{'=' * 80}\n")

            # Show final positions
            final_positions = get_current_positions(connector)
            if not final_positions:
                logger.info("✓ Account cleared - no positions remaining")
            else:
                logger.warning(f"⚠ {len(final_positions)} position(s) still remaining (may take time to settle)")

        return True

    except IBConnectionError as e:
        logger.error(f"Connection error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return False
    finally:
        connector.disconnect()
        logger.info("Disconnected from IB")


def main():
    parser = argparse.ArgumentParser(
        description="Clear all positions from IB paper trading account"
    )
    parser.add_argument(
        "--portfolio-id",
        type=int,
        required=True,
        help="Portfolio ID to use for IB connection"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually submitting orders"
    )

    args = parser.parse_args()

    logger.info(f"\n{'=' * 80}")
    logger.info("IB POSITION CLEARER")
    logger.info(f"{'=' * 80}\n")

    if args.dry_run:
        logger.info("⚠ DRY RUN MODE - No orders will be submitted\n")

    success = clear_all_positions(args.portfolio_id, args.dry_run)

    if success:
        logger.info("\n✓ Script completed successfully")
        sys.exit(0)
    else:
        logger.error("\n✗ Script failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
