"""
Interactive Brokers order monitoring task.

Runs periodically during market hours to check order status and process fills.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from celery import shared_task

from zimuabull.daytrading.ib_connector import IBConnectionError, IBConnector
from zimuabull.models import (
    DayTradePosition,
    DayTradePositionStatus,
    IBOrder,
    IBOrderStatus,
    Portfolio,
    PortfolioTransaction,
    TransactionType,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=False, queue="pidashtasks")
def monitor_ib_orders(self):
    """
    Monitor all active IB orders and process fills.

    Runs every 30 seconds during market hours.
    Updates order status, creates transactions, and updates positions.
    """
    # Get all active orders
    active_orders = IBOrder.objects.filter(
        status__in=[IBOrderStatus.PENDING, IBOrderStatus.SUBMITTED, IBOrderStatus.PARTIALLY_FILLED]
    ).select_related("portfolio", "symbol", "day_trade_position")

    if not active_orders.exists():
        return {"status": "no_active_orders"}

    results = {
        "checked": 0,
        "filled": 0,
        "partially_filled": 0,
        "cancelled": 0,
        "rejected": 0,
        "errors": 0,
    }

    # Group orders by portfolio to reuse connections
    orders_by_portfolio = {}
    for order in active_orders:
        portfolio_id = order.portfolio_id
        if portfolio_id not in orders_by_portfolio:
            orders_by_portfolio[portfolio_id] = []
        orders_by_portfolio[portfolio_id].append(order)

    # Process orders for each portfolio
    for portfolio_id, orders in orders_by_portfolio.items():
        try:
            portfolio = Portfolio.objects.get(id=portfolio_id)

            # Skip if IB not enabled
            if not portfolio.use_interactive_brokers:
                continue

            # Connect to IB
            connector = IBConnector(portfolio)
            connector.connect()

            try:
                for order in orders:
                    results["checked"] += 1
                    _process_order(connector, order, results)
            finally:
                connector.disconnect()

        except Exception as e:
            logger.error(
                f"Error processing orders for portfolio {portfolio_id}: {e}",
                exc_info=True
            )
            results["errors"] += 1

    return results


def _process_order(connector: IBConnector, order: IBOrder, results: dict):
    """
    Process a single IB order.

    Checks status and handles fills, partial fills, cancellations, and rejections.
    Uses trade.fills list for accurate execution data.
    """
    try:
        # Get order status from IB
        trade = connector.get_order_status(order.ib_order_id)

        if not trade:
            logger.warning(f"Order {order.ib_order_id} not found in IB")
            return

        ib_status = trade.orderStatus.status

        # Calculate filled quantity and average price from fills list
        total_filled_qty = 0.0
        total_value = 0.0
        total_commission = 0.0

        if trade.fills:
            for fill in trade.fills:
                qty = float(fill.execution.shares)
                price = float(fill.execution.price)
                total_filled_qty += qty
                total_value += (qty * price)

                # Get commission from commissionReport if available
                if fill.commissionReport:
                    total_commission += abs(float(fill.commissionReport.commission))

            # Calculate average fill price
            avg_fill_price = total_value / total_filled_qty if total_filled_qty > 0 else 0.0
        else:
            # Fallback to orderStatus if no fills yet
            total_filled_qty = float(trade.orderStatus.filled)
            avg_fill_price = float(trade.orderStatus.avgFillPrice) if trade.orderStatus.avgFillPrice > 0 else 0.0
            if trade.orderStatus.commission:
                total_commission = abs(float(trade.orderStatus.commission))

        remaining_qty = float(trade.orderStatus.remaining)

        logger.debug(
            f"Order {order.ib_order_id}: status={ib_status}, "
            f"filled={total_filled_qty}, remaining={remaining_qty}, "
            f"avg_fill_price={avg_fill_price}, commission={total_commission}, "
            f"fills_count={len(trade.fills) if trade.fills else 0}"
        )

        # Handle different statuses
        if ib_status in ["Filled", "ApiDone"]:
            _handle_filled_order(order, total_filled_qty, avg_fill_price, total_commission, trade, results)

        elif ib_status == "PartiallyFilled":
            _handle_partially_filled_order(order, total_filled_qty, remaining_qty, avg_fill_price, total_commission, results)

        elif ib_status in ["Cancelled", "ApiCancelled"]:
            _handle_cancelled_order(order, results)

        elif ib_status in ["Inactive", "PendingCancel"]:
            # Order is being cancelled, wait for final status
            order.status_message = f"IB Status: {ib_status}"
            order.save(update_fields=["status_message", "updated_at"])

        elif ib_status in ["Submitted", "PreSubmitted", "PendingSubmit"]:
            # Order is still active, update message
            order.status = IBOrderStatus.SUBMITTED
            order.status_message = f"IB Status: {ib_status}"
            order.save(update_fields=["status", "status_message", "updated_at"])

        else:
            # Unknown or error status
            logger.warning(f"Unexpected order status for {order.ib_order_id}: {ib_status}")
            order.status_message = f"Unexpected status: {ib_status}"
            order.save(update_fields=["status_message", "updated_at"])

    except Exception as e:
        logger.error(
            f"Error processing order {order.client_order_id}: {e}",
            exc_info=True
        )
        order.error_message = str(e)
        order.save(update_fields=["error_message", "updated_at"])


def _handle_filled_order(order: IBOrder, filled_qty: float, avg_fill_price: float, commission: float, trade, results: dict):
    """Handle a completely filled order"""
    with transaction.atomic():
        # Update order
        order.status = IBOrderStatus.FILLED
        order.filled_quantity = Decimal(str(filled_qty))
        order.filled_price = Decimal(str(avg_fill_price))
        order.filled_at = timezone.now()
        order.remaining_quantity = Decimal("0")

        # Set commission from fills
        if commission > 0:
            order.commission = Decimal(str(commission))

        order.status_message = "Order filled"
        order.save()

        logger.info(
            f"Order {order.client_order_id} FILLED: "
            f"{filled_qty} shares @ ${avg_fill_price}"
        )

        # Create transaction
        txn_type = TransactionType.BUY if order.action == "BUY" else TransactionType.SELL
        txn = PortfolioTransaction(
            portfolio=order.portfolio,
            symbol=order.symbol,
            transaction_type=txn_type,
            quantity=order.filled_quantity,
            price=order.filled_price,
            transaction_date=timezone.now().date(),
            notes=f"IB Order {order.ib_order_id}: {order.client_order_id}",
        )
        txn.save()

        # Update position
        if order.day_trade_position:
            position = order.day_trade_position

            if order.action == "BUY":
                # BUY order filled - update position to OPEN
                position.status = DayTradePositionStatus.OPEN
                position.entry_price = order.filled_price
                position.shares = order.filled_quantity
                position.entry_time = timezone.now()
                position.save(update_fields=["status", "entry_price", "shares", "entry_time", "updated_at"])

                logger.info(f"Position {position.id} opened: {position.shares} shares @ ${position.entry_price}")

            elif order.action == "SELL":
                # SELL order filled - update position to CLOSED
                position.status = DayTradePositionStatus.CLOSED
                position.exit_price = order.filled_price
                position.exit_time = timezone.now()
                position.save(update_fields=["status", "exit_price", "exit_time", "updated_at"])

                logger.info(f"Position {position.id} closed: {position.shares} shares @ ${position.exit_price}")

        results["filled"] += 1


def _handle_partially_filled_order(
    order: IBOrder,
    filled_qty: float,
    remaining_qty: float,
    avg_fill_price: float,
    commission: float,
    results: dict
):
    """Handle a partially filled order"""
    # Update order status
    order.status = IBOrderStatus.PARTIALLY_FILLED
    order.filled_quantity = Decimal(str(filled_qty))
    order.remaining_quantity = Decimal(str(remaining_qty))
    if avg_fill_price > 0:
        order.filled_price = Decimal(str(avg_fill_price))
    if commission > 0:
        order.commission = Decimal(str(commission))
    order.status_message = f"Partially filled: {filled_qty}/{float(order.quantity)}"
    order.save()

    logger.info(
        f"Order {order.client_order_id} PARTIALLY FILLED: "
        f"{filled_qty} of {order.quantity} shares"
    )

    results["partially_filled"] += 1


def _handle_cancelled_order(order: IBOrder, results: dict):
    """Handle a cancelled order"""
    order.status = IBOrderStatus.CANCELLED
    order.status_message = "Order cancelled"
    order.save()

    logger.info(f"Order {order.client_order_id} CANCELLED")

    # If this was a pending BUY order, cancel the position too
    if order.day_trade_position and order.action == "BUY":
        position = order.day_trade_position
        if position.status == DayTradePositionStatus.PENDING:
            position.status = DayTradePositionStatus.CANCELLED
            position.notes = f"Order cancelled: {order.status_message}"
            position.save(update_fields=["status", "notes", "updated_at"])
            logger.info(f"Position {position.id} cancelled due to order cancellation")

    results["cancelled"] += 1


@shared_task(bind=True, ignore_result=False, queue="pidashtasks")
def cancel_stale_ib_orders(self):
    """
    Cancel IB orders that have been pending for too long.

    Orders pending for more than 10 minutes are considered stale and cancelled.
    """
    from datetime import timedelta

    cutoff_time = timezone.now() - timedelta(minutes=10)

    stale_orders = IBOrder.objects.filter(
        status__in=[IBOrderStatus.PENDING, IBOrderStatus.SUBMITTED],
        submitted_at__lt=cutoff_time
    ).select_related("portfolio", "symbol")

    if not stale_orders.exists():
        return {"status": "no_stale_orders"}

    cancelled_count = 0
    error_count = 0

    for order in stale_orders:
        try:
            if not order.portfolio.use_interactive_brokers:
                continue

            connector = IBConnector(order.portfolio)
            connector.connect()

            try:
                success = connector.cancel_order(order.ib_order_id)
                if success:
                    order.status = IBOrderStatus.CANCELLED
                    order.status_message = "Cancelled: order timeout (>10 minutes)"
                    order.save()
                    cancelled_count += 1
                else:
                    error_count += 1
            finally:
                connector.disconnect()

        except Exception as e:
            logger.error(
                f"Error cancelling stale order {order.client_order_id}: {e}",
                exc_info=True
            )
            error_count += 1

    return {
        "status": "completed",
        "cancelled": cancelled_count,
        "errors": error_count
    }
