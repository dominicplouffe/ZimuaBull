#!/usr/bin/env python
"""
Clear all positions from Interactive Brokers paper trading account.

This script:
1. Connects directly to IB Gateway/TWS
2. Fetches all current positions
3. Submits SELL market orders for each position
4. Waits for order confirmations

Usage:
    python clear_ib_positions.py
    python clear_ib_positions.py --dry-run  # Test without submitting orders
    python clear_ib_positions.py --host localhost --port 7497 --client-id 1
"""

import argparse
import logging
import sys
import time

from ib_insync import IB, MarketOrder, Stock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def clear_all_positions(host: str = "localhost", port: int = 7497, client_id: int = 1, dry_run: bool = False):
    """
    Clear all positions from the IB account.

    Args:
        host: IB Gateway/TWS host (default: localhost)
        port: IB Gateway/TWS port (default: 7497 for paper trading)
        client_id: IB API client ID (default: 1)
        dry_run: If True, only show what would be done without submitting orders
    """
    ib = IB()

    try:
        # Connect to IB
        logger.info(f"Connecting to IB at {host}:{port} with client_id={client_id}...")
        ib.connect(host=host, port=port, clientId=client_id, timeout=20)
        logger.info("✓ Connected to IB")

        # Get all positions
        logger.info("\nFetching current positions...")
        positions = ib.positions()

        if not positions:
            logger.info("✓ No positions found in IB account")
            return True

        logger.info(f"Found {len(positions)} position(s) in IB account:")
        for pos in positions:
            logger.info(f"  - {pos.contract.symbol} ({pos.contract.exchange}): {pos.position} shares @ avg cost {pos.avgCost}")

        # Submit SELL orders for each position
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Processing {len(positions)} position(s)...")
        logger.info(f"{'=' * 80}\n")

        submitted_trades = []

        for pos in positions:
            symbol = pos.contract.symbol
            quantity = abs(pos.position)  # Use absolute value (make positive)

            # Skip if quantity is zero or negative (short positions)
            if pos.position <= 0:
                logger.warning(f"Skipping {symbol}: position is {pos.position} (zero or short)")
                continue

            logger.info(f"Processing {symbol}: {quantity} shares")

            if dry_run:
                logger.info(f"  [DRY RUN] Would submit SELL market order for {quantity} shares")
                continue

            try:
                # Recreate contract with SMART routing to avoid direct routing fees/restrictions
                contract = Stock(symbol, "SMART", "USD")
                ib.qualifyContracts(contract)

                # Create SELL market order
                order = MarketOrder("SELL", quantity)

                # Submit order
                logger.info(f"  Submitting SELL market order for {quantity} shares...")
                trade = ib.placeOrder(contract, order)

                submitted_trades.append({
                    "symbol": symbol,
                    "quantity": quantity,
                    "trade": trade
                })

                logger.info(f"  ✓ Order submitted (Order ID: {trade.order.orderId})")

                # Small delay between orders
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"  ✗ Failed to submit order for {symbol}: {e}")

        if dry_run:
            logger.info(f"\n{'=' * 80}")
            logger.info("DRY RUN COMPLETE - No orders were actually submitted")
            logger.info(f"{'=' * 80}\n")
            return True

        # Wait for order confirmations
        if submitted_trades:
            logger.info(f"\n{'=' * 80}")
            logger.info(f"Waiting for order confirmations...")
            logger.info(f"{'=' * 80}\n")

            # Wait and check order status multiple times
            for i in range(6):  # Check 6 times over 30 seconds
                ib.sleep(5)

                logger.info(f"Checking order status... ({(i+1)*5}s)")

                for order_info in submitted_trades:
                    trade = order_info["trade"]
                    status = trade.orderStatus.status
                    filled = trade.orderStatus.filled

                    logger.info(f"  {order_info['symbol']}: {status} ({filled}/{order_info['quantity']} filled)")

            logger.info(f"\n{'=' * 80}")
            logger.info("✓ Order monitoring complete")
            logger.info(f"{'=' * 80}\n")

            # Show final positions
            logger.info("Fetching final positions...")
            final_positions = ib.positions()

            if not final_positions:
                logger.info("✓ Account cleared - no positions remaining")
            else:
                logger.warning(f"⚠ {len(final_positions)} position(s) still remaining:")
                for pos in final_positions:
                    logger.warning(f"  - {pos.contract.symbol}: {pos.position} shares")

        return True

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return False

    finally:
        if ib.isConnected():
            ib.disconnect()
            logger.info("Disconnected from IB")


def main():
    parser = argparse.ArgumentParser(
        description="Clear all positions from IB paper trading account"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="192.168.0.85",
        help="IB Gateway/TWS host (default: 192.168.0.85)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=4002,
        help="IB Gateway/TWS port (default: 4002 for paper trading)"
    )
    parser.add_argument(
        "--client-id",
        type=int,
        default=1,
        help="IB API client ID (default: 1)"
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

    success = clear_all_positions(
        host=args.host,
        port=args.port,
        client_id=args.client_id,
        dry_run=args.dry_run
    )

    if success:
        logger.info("\n✓ Script completed successfully")
        sys.exit(0)
    else:
        logger.error("\n✗ Script failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
