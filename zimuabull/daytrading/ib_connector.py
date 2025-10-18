"""
Interactive Brokers connection management using ib_insync.

Handles connection lifecycle, order submission, and status tracking.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ib_insync import IB, Contract, MarketOrder, Order, Stock, Trade

if TYPE_CHECKING:
    from zimuabull.models import Portfolio, Symbol

logger = logging.getLogger(__name__)


class IBConnectionError(Exception):
    """Raised when IB connection fails"""

    pass


class IBOrderError(Exception):
    """Raised when order submission fails"""

    pass


class IBConnector:
    """
    Manages connection to Interactive Brokers Gateway/TWS.

    Each portfolio should have its own connector instance with unique client_id.
    """

    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio
        self.ib = IB()
        self._connected = False

        # Validate portfolio has IB configuration
        if not portfolio.use_interactive_brokers:
            raise ValueError(f"Portfolio {portfolio.id} does not have IB enabled")

        if not portfolio.ib_host or not portfolio.ib_port or not portfolio.ib_client_id:
            raise ValueError(f"Portfolio {portfolio.id} missing IB configuration")

    def connect(self) -> bool:
        """
        Connect to IB Gateway/TWS.

        Returns:
            True if connected successfully

        Raises:
            IBConnectionError if connection fails
        """
        if self._connected:
            return True

        try:
            host = self.portfolio.ib_host
            port = self.portfolio.ib_port
            client_id = self.portfolio.ib_client_id

            logger.info(
                f"Connecting to IB Gateway at {host}:{port} with client_id={client_id} "
                f"for portfolio {self.portfolio.id} ({self.portfolio.name})"
            )

            self.ib.connect(host=host, port=port, clientId=client_id, timeout=20)

            self._connected = True
            logger.info(f"Successfully connected to IB for portfolio {self.portfolio.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to IB for portfolio {self.portfolio.id}: {e}")
            raise IBConnectionError(f"Connection failed: {e}") from e

    def disconnect(self):
        """Disconnect from IB Gateway/TWS"""
        if self._connected:
            try:
                self.ib.disconnect()
                self._connected = False
                logger.info(f"Disconnected from IB for portfolio {self.portfolio.id}")
            except Exception as e:
                logger.warning(f"Error during IB disconnect for portfolio {self.portfolio.id}: {e}")

    def is_connected(self) -> bool:
        """Check if currently connected to IB"""
        return self._connected and self.ib.isConnected()

    def create_contract(self, symbol: Symbol) -> Contract:
        """
        Create IB contract for a symbol.

        Args:
            symbol: Symbol model instance

        Returns:
            ib_insync Contract object
        """
        exchange_code = symbol.exchange.code.upper()

        # Map exchange codes to IB exchange names
        if exchange_code in {"TSE", "TO"}:
            ib_exchange = "TSE"
            ib_symbol = symbol.symbol.replace(".TO", "")
        elif exchange_code == "NASDAQ":
            ib_exchange = "SMART"  # SMART routing for US stocks
            ib_symbol = symbol.symbol
        elif exchange_code == "NYSE":
            ib_exchange = "SMART"
            ib_symbol = symbol.symbol
        else:
            # Default to SMART routing for unknown exchanges
            ib_exchange = "SMART"
            ib_symbol = symbol.symbol

        contract = Stock(ib_symbol, ib_exchange, "USD")
        return contract

    def submit_market_order(self, symbol: Symbol, action: str, quantity: Decimal, account: str | None = None) -> Trade:
        """
        Submit a market order to IB.

        Args:
            symbol: Symbol to trade
            action: "BUY" or "SELL"
            quantity: Number of shares (can be fractional)
            account: Optional account override

        Returns:
            ib_insync Trade object

        Raises:
            IBOrderError if order submission fails
        """
        if not self.is_connected():
            raise IBConnectionError("Not connected to IB")

        try:
            contract = self.create_contract(symbol)

            # Qualify the contract to ensure it's valid
            self.ib.qualifyContracts(contract)

            # Create market order
            order = MarketOrder(action, float(quantity))

            # Set account if specified
            if account or self.portfolio.ib_account:
                order.account = account or self.portfolio.ib_account

            # Submit order
            logger.info(
                f"Submitting {action} market order: {quantity} shares of {symbol.symbol} "
                f"for portfolio {self.portfolio.id}"
            )

            trade = self.ib.placeOrder(contract, order)

            logger.info(
                f"Order submitted successfully. Contract ID: {trade.contract.conId}, PermID: {trade.order.permId}"
            )

            return trade

        except Exception as e:
            logger.error(f"Failed to submit order for {symbol.symbol}: {e}", exc_info=True)
            raise IBOrderError(f"Order submission failed: {e}") from e

    def get_order_status(self, order_id: int) -> Trade | None:
        """
        Get current status of an order.

        Args:
            order_id: IB order ID

        Returns:
            Trade object if found, None otherwise
        """
        if not self.is_connected():
            return None

        # Get all trades
        trades = self.ib.trades()

        # Find matching trade
        for trade in trades:
            if trade.contract.conId == order_id:
                return trade
            if len(trade.fills) > 0:
                for fill in trade.fills:
                    if fill.execution.orderId == order_id:
                        return trade
        return None

    def cancel_order(self, order_id: int) -> bool:
        """
        Cancel an order.

        Args:
            order_id: IB order ID

        Returns:
            True if cancellation requested successfully
        """
        if not self.is_connected():
            return False

        try:
            trade = self.get_order_status(order_id)
            if trade:
                self.ib.cancelOrder(trade.order)
                logger.info(f"Cancelled order {order_id}")
                return True
            else:
                logger.warning(f"Order {order_id} not found for cancellation")
                return False
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def get_account_summary(self) -> dict:
        """
        Get account summary information.

        Returns:
            Dict with account info (buying power, net liquidation, etc.)
        """
        if not self.is_connected():
            raise IBConnectionError("Not connected to IB")

        account = self.portfolio.ib_account or ""
        summary = self.ib.accountSummary(account)

        result = {}
        for item in summary:
            result[item.tag] = {"value": item.value, "currency": item.currency, "account": item.account}

        return result


@contextmanager
def ib_connection(portfolio: Portfolio):
    """
    Context manager for IB connections.

    Usage:
        with ib_connection(portfolio) as connector:
            connector.submit_market_order(...)
    """
    connector = IBConnector(portfolio)
    try:
        connector.connect()
        yield connector
    finally:
        connector.disconnect()


def validate_ib_configuration(portfolio: Portfolio) -> tuple[bool, str]:
    """
    Validate that portfolio IB configuration is correct.

    Args:
        portfolio: Portfolio to validate

    Returns:
        (is_valid, error_message) tuple
    """
    if not portfolio.use_interactive_brokers:
        return False, "Interactive Brokers not enabled"

    if not portfolio.ib_host:
        return False, "IB host not configured"

    if not portfolio.ib_port:
        return False, "IB port not configured"

    if not portfolio.ib_client_id:
        return False, "IB client ID not configured"

    # Try to connect
    try:
        connector = IBConnector(portfolio)
        connector.connect()
        connector.disconnect()
        return True, "Configuration valid"
    except Exception as e:
        return False, f"Connection test failed: {e}"
