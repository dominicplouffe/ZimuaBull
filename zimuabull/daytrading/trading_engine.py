from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone as dj_timezone

import numpy as np
import pandas as pd
import yfinance as yf

from zimuabull.daytrading.dataset import build_dataset
from zimuabull.daytrading.feature_builder import build_feature_snapshot
from zimuabull.daytrading.ib_connector import IBConnectionError, IBConnector, IBOrderError
from zimuabull.daytrading.modeling import load_model, prepare_features_for_inference
from zimuabull.models import (
    DayTradePosition,
    DayTradePositionStatus,
    DayTradingRecommendation,
    IBOrder,
    IBOrderAction,
    IBOrderStatus,
    IBOrderType,
    Portfolio,
    PortfolioSnapshot,
    PortfolioTransaction,
    Symbol,
    TransactionType,
)
from zimuabull.services.market_regime import get_regime_adjustments_for_portfolio

logger = logging.getLogger(__name__)

NY_TZ = ZoneInfo("America/New_York")


def is_market_open() -> bool:
    """
    Check if US stock market is currently open.

    NYSE/NASDAQ hours: 9:30 AM - 4:00 PM ET, Monday-Friday
    """
    from datetime import time

    now = dj_timezone.now().astimezone(NY_TZ)

    # Weekend check
    if now.weekday() >= 5:
        return False

    # Market hours check
    market_open = time(9, 30)
    market_close = time(16, 0)

    current_time = now.time()
    if current_time < market_open or current_time >= market_close:
        return False

    return True


# Transaction costs configuration (based on Interactive Brokers tiered pricing)
def calculate_commission_per_share(monthly_volume: int) -> float:
    """
    Calculate commission per share based on monthly volume.

    Monthly Volume (shares) | USD per share
    ≤ 300,000              | 0.0035
    300,001 - 3,000,000    | 0.0020
    3,000,001 - 20,000,000 | 0.0015
    20,000,001 - 100,000,000 | 0.0010
    > 100,000,000          | 0.0005
    """
    if monthly_volume <= 300_000:
        return 0.0035
    if monthly_volume <= 3_000_000:
        return 0.0020
    if monthly_volume <= 20_000_000:
        return 0.0015
    if monthly_volume <= 100_000_000:
        return 0.0010
    return 0.0005


# Conservative estimate for low volume (tier 1)
COMMISSION_PER_SHARE = 0.0035
SLIPPAGE_BPS = 5  # 0.05% slippage per trade


@dataclass
class Recommendation:
    symbol: Symbol
    predicted_return: float
    confidence_score: float
    entry_price: float
    target_price: float
    stop_price: float
    allocation: Decimal
    shares: Decimal
    atr: float
    features: dict


def get_portfolios_for_user(user_id: int) -> list[Portfolio]:
    """Get all active portfolios for a user (for backward compatibility)"""
    portfolios = list(
        Portfolio.objects.filter(user_id=user_id, is_active=True)
        .order_by("created_at")
    )
    if not portfolios:
        msg = f"No active portfolio found for user {user_id}."
        raise ValueError(msg)
    return portfolios


def get_portfolio_for_user(user_id: int) -> Portfolio:
    return get_portfolios_for_user(user_id)[0]


def get_automated_portfolios() -> list[Portfolio]:
    """Get all active portfolios with automated trading enabled"""
    return list(
        Portfolio.objects.filter(is_active=True, is_automated=True)
        .select_related("exchange", "user")
        .order_by("created_at")
    )


def get_manual_portfolios() -> list[Portfolio]:
    """Get all active portfolios with manual tracking (not automated)"""
    return list(
        Portfolio.objects.filter(is_active=True, is_automated=False)
        .select_related("exchange", "user")
        .order_by("created_at")
    )


def _yf_symbol(symbol: Symbol) -> str:
    exchange = symbol.exchange.code.upper()
    if exchange in {"TSE", "TO"}:
        return f"{symbol.symbol}.TO"
    return symbol.symbol


def fetch_live_price(symbol: Symbol) -> float | None:
    try:
        ticker = yf.Ticker(_yf_symbol(symbol))
        live_price = ticker.fast_info.get("lastPrice")
        if not live_price:
            info = ticker.info
            live_price = info.get("regularMarketPrice") or info.get("currentPrice")
        if not live_price:
            hist = ticker.history(period="1d")
            if not hist.empty:
                live_price = hist["Close"].iloc[-1]
        return float(live_price) if live_price else None
    except Exception:
        return None


def _calculate_stop_target(
    entry_price: float,
    atr: float | None,
    predicted_return: float,
    min_rr_ratio: float = 1.5
) -> tuple[float, float]:
    """
    Calculate stop loss and target prices using ATR-based risk management.

    Args:
        entry_price: Entry price for the position
        atr: Average True Range (14-day)
        predicted_return: Model's predicted intraday return
        min_rr_ratio: Minimum reward:risk ratio (default 1.5:1)

    Returns:
        (stop_price, target_price) tuple
    """
    # Use 2 ATRs for stop loss (industry standard)
    if atr is None or np.isnan(atr):
        atr = entry_price * 0.015  # 1.5% default ATR

    # Stop distance = 2 * ATR
    stop_distance = max(0.01, 2 * atr / entry_price)  # Minimum 1% stop

    # Target based on prediction, but enforce minimum R:R ratio
    target_distance = max(
        stop_distance * min_rr_ratio,  # Minimum reward:risk ratio
        abs(predicted_return) * 1.2     # 120% of model prediction
    )

    stop_price = entry_price * (1 - stop_distance)
    target_price = entry_price * (1 + target_distance)

    return stop_price, target_price


def _sanitize_prediction(value: float) -> float:
    if value is None or np.isnan(value):
        return 0.0
    return float(value)


def _confidence_score(predicted_return: float, volatility: float | None) -> float:
    """
    Calculate confidence score using Sharpe-like ratio with sigmoid scaling.

    Returns score between 0-100 where:
    - 50 = neutral prediction
    - >70 = high confidence
    - <30 = low confidence
    """
    if volatility is None or np.isnan(volatility) or volatility == 0:
        # Fallback: simple linear scaling
        raw_score = predicted_return * 5000  # Scale to reasonable range
        return max(0.0, min(100.0, 50 + raw_score))

    # Sharpe-like ratio: return divided by risk
    sharpe_score = predicted_return / max(volatility, 1e-6)

    # Sigmoid scaling to map to 0-100 range
    # sigmoid(x) = 1 / (1 + exp(-x))
    # Scale factor of 5 gives good sensitivity
    confidence = 100 / (1 + np.exp(-5 * sharpe_score))

    return float(confidence)


def _prepare_dataset(trade_date: date, symbols: Iterable[Symbol]) -> pd.DataFrame:
    snapshots = []
    for symbol in symbols:
        snap = build_feature_snapshot(symbol, trade_date, overwrite=False)
        if snap:
            snapshots.append(snap)
    if not snapshots:
        return pd.DataFrame()

    dataset = build_dataset(snapshots, drop_na=False)
    dataset.features["symbol"] = dataset.metadata["symbol"]
    dataset.features["exchange"] = dataset.metadata["exchange"]
    dataset.features["trade_date"] = dataset.metadata["trade_date"]
    dataset.features["intraday_return"] = dataset.metadata.get("intraday_return")
    return dataset.features


def generate_recommendations(
    trade_date: date,
    portfolio: Portfolio,
    max_positions: int | None = None,
    bankroll: float | None = None,
    exchange_filter: str | None = None,
) -> list[Recommendation]:
    """
    Generate trading recommendations for a portfolio.

    Args:
        trade_date: The date to generate recommendations for
        portfolio: Portfolio object containing trading settings
        max_positions: Override for max positions (uses portfolio.dt_max_recommendations if None)
        bankroll: Override for bankroll (uses portfolio.cash_balance if None)
        exchange_filter: Optional exchange filter (uses portfolio.exchange.code if None)
    """
    # Use portfolio settings if not overridden
    if max_positions is None:
        max_positions = portfolio.dt_max_recommendations
    if bankroll is None:
        bankroll = float(portfolio.cash_balance)
    if exchange_filter is None:
        exchange_filter = portfolio.exchange.code

    # Extract portfolio-specific settings
    max_position_percent = float(portfolio.dt_max_position_percent)
    per_trade_risk_fraction = float(portfolio.dt_per_trade_risk_fraction)
    allow_fractional_shares = portfolio.dt_allow_fractional_shares

    regime_adjustments = get_regime_adjustments_for_portfolio(portfolio, trade_date)
    regime_confidence_thresholds = {
        "BULL_TRENDING": 55.0,
        "BEAR_TRENDING": 72.0,
        "HIGH_VOL": 70.0,
        "LOW_VOL": 50.0,
        "RANGING": 60.0,
    }
    confidence_threshold = regime_confidence_thresholds.get(regime_adjustments.regime, 60.0)

    if regime_adjustments.max_positions:
        max_positions = max(1, min(max_positions, int(regime_adjustments.max_positions)))
    if regime_adjustments.risk_per_trade:
        per_trade_risk_fraction = max(0.001, min(per_trade_risk_fraction, float(regime_adjustments.risk_per_trade)))
    symbols = Symbol.objects.all()
    if exchange_filter:
        symbols = symbols.filter(exchange__code=exchange_filter)
    symbols = symbols.filter(last_volume__gt=100000)

    dataset_df = _prepare_dataset(trade_date, symbols)
    if dataset_df.empty:
        return []

    # Load model with imputer (new API)
    model, trained_columns, imputer = load_model()

    feature_df = dataset_df.drop(columns=["symbol", "exchange", "trade_date", "intraday_return"], errors="ignore")
    encoded = prepare_features_for_inference(feature_df, trained_columns, imputer)
    predictions = model.predict(encoded)

    dataset_df["predicted_return"] = predictions

    recommendations: list[Recommendation] = []
    for _, row in dataset_df.iterrows():
        symbol_obj = Symbol.objects.get(symbol=row["symbol"], exchange__code=row["exchange"])
        predicted_return = _sanitize_prediction(row["predicted_return"])
        if predicted_return <= 0:
            continue
        volatility = row.get("volatility_10d") or row.get("volatility_20d")
        confidence = _confidence_score(predicted_return, volatility)
        entry_price = float(row.get("previous_close") or symbol_obj.last_close)

        if confidence < confidence_threshold:
            continue

        stop_price, target_price = _calculate_stop_target(entry_price, row.get("atr_14"), predicted_return)

        atr_value = row.get("atr_14") if row.get("atr_14") is not None else entry_price * 0.01
        risk_per_share = entry_price - stop_price
        if risk_per_share <= 0:
            continue
        max_risk_capital = bankroll * per_trade_risk_fraction
        shares_by_risk = max_risk_capital / risk_per_share
        max_allocation = bankroll * max_position_percent
        allocation = min(max_allocation, bankroll / max_positions)
        shares = allocation / entry_price
        shares = min(shares, shares_by_risk)

        # Round to whole shares if fractional shares are not allowed
        if not allow_fractional_shares:
            shares = int(shares)  # Floor to whole number

        if shares < 1:
            continue

        # Format shares precision based on fractional flag
        shares_decimal = Decimal(str(shares)) if allow_fractional_shares else Decimal(str(int(shares)))

        recommendation = Recommendation(
            symbol=symbol_obj,
            predicted_return=predicted_return,
            confidence_score=confidence,
            entry_price=entry_price,
            target_price=target_price,
            stop_price=stop_price,
            allocation=Decimal(str(allocation)),
            shares=shares_decimal,
            atr=float(atr_value),
            features=row.to_dict(),
        )
        recommendations.append(recommendation)

    recommendations.sort(key=lambda rec: rec.confidence_score, reverse=True)
    return recommendations[:max_positions]


def _record_recommendation(trade_date: date, recommendation: Recommendation, rank: int):
    DayTradingRecommendation.objects.update_or_create(
        symbol=recommendation.symbol,
        recommendation_date=trade_date,
        defaults={
            "rank": rank,
            "confidence_score": recommendation.confidence_score,
            "recommended_allocation": recommendation.allocation,
            "entry_price": recommendation.entry_price,
            "target_price": recommendation.target_price,
            "stop_loss_price": recommendation.stop_price,
            "signal_score": recommendation.features.get("obv_status_num", 0) * 10,
            "momentum_score": recommendation.features.get("momentum_5d", 0) * 100,
            "volume_score": recommendation.features.get("volume_ratio_5d", 0) * 10 if recommendation.features.get("volume_ratio_5d") else 0,
            "prediction_score": recommendation.predicted_return * 100,
            "technical_score": recommendation.features.get("rsi", 0) or 0,
            "recommendation_reason": f"Model predicted return {recommendation.predicted_return:.2%} with confidence {recommendation.confidence_score:.1f}",
        },
    )


def _create_transaction(
    portfolio: Portfolio,
    symbol: Symbol,
    quantity: Decimal,
    price: Decimal,
    transaction_date: date,
    notes: str,
):
    # Use save() instead of create() to trigger holding updates
    txn = PortfolioTransaction(
        portfolio=portfolio,
        symbol=symbol,
        transaction_type=TransactionType.BUY,
        quantity=quantity,
        price=price,
        transaction_date=transaction_date,
        notes=notes,
    )
    txn.save()


def _create_day_trade_position(
    portfolio: Portfolio,
    recommendation: Recommendation,
    trade_date: date,
    filled_price: Decimal,
    filled_shares: Decimal,
    rank: int,
):
    DayTradePosition.objects.create(
        portfolio=portfolio,
        symbol=recommendation.symbol,
        trade_date=trade_date,
        shares=filled_shares,
        allocation=recommendation.allocation,
        entry_price=filled_price,
        entry_time=dj_timezone.now(),
        target_price=recommendation.target_price,
        stop_price=recommendation.stop_price,
        confidence_score=recommendation.confidence_score,
        predicted_return=recommendation.predicted_return,
        recommendation_rank=rank,
    )


def _submit_ib_buy_order(
    connector: IBConnector,
    portfolio: Portfolio,
    symbol: Symbol,
    shares: Decimal,
    trade_date: date,
    rank: int,
) -> IBOrder | None:
    """
    Submit a BUY market order to Interactive Brokers.

    Returns:
        IBOrder if submitted successfully, None otherwise
    """
    try:
        # Generate unique client order ID
        client_order_id = f"BUY_{portfolio.id}_{symbol.id}_{trade_date}_{uuid.uuid4().hex[:8]}"

        # Submit to IB
        trade = connector.submit_market_order(
            symbol=symbol,
            action="BUY",
            quantity=shares
        )

        # Create IBOrder record
        ib_order = IBOrder.objects.create(
            portfolio=portfolio,
            symbol=symbol,
            client_order_id=client_order_id,
            ib_order_id=trade.contract.conId,
            ib_perm_id=trade.order.permId,
            action=IBOrderAction.BUY,
            order_type=IBOrderType.MARKET,
            quantity=shares,
            status=IBOrderStatus.SUBMITTED,
            submitted_at=dj_timezone.now(),
            status_message=f"Rank {rank} - Submitted to IB"
        )

        logger.info(
            f"IB BUY order submitted: {client_order_id}, "
            f"IB Order ID: {trade.order.orderId}, "
            f"{shares} shares of {symbol.symbol}"
        )

        return ib_order

    except (IBConnectionError, IBOrderError) as e:
        logger.error(
            f"Failed to submit IB BUY order for {symbol.symbol}: {e}",
            exc_info=True
        )
        return None


def _submit_ib_sell_order(
    connector: IBConnector,
    portfolio: Portfolio,
    position: DayTradePosition,
    exit_reason: str,
) -> IBOrder | None:
    """
    Submit a SELL market order to Interactive Brokers.

    Returns:
        IBOrder if submitted successfully, None otherwise
    """
    try:
        # Generate unique client order ID
        client_order_id = f"SELL_{portfolio.id}_{position.symbol.id}_{position.trade_date}_{uuid.uuid4().hex[:8]}"

        # Submit to IB
        trade = connector.submit_market_order(
            symbol=position.symbol,
            action="SELL",
            quantity=position.shares
        )

        # Create IBOrder record
        ib_order = IBOrder.objects.create(
            portfolio=portfolio,
            day_trade_position=position,
            symbol=position.symbol,
            client_order_id=client_order_id,
            ib_order_id=trade.order.orderId,
            ib_perm_id=trade.order.permId,
            action=IBOrderAction.SELL,
            order_type=IBOrderType.MARKET,
            quantity=position.shares,
            status=IBOrderStatus.SUBMITTED,
            submitted_at=dj_timezone.now(),
            status_message=f"Exit reason: {exit_reason}"
        )

        logger.info(
            f"IB SELL order submitted: {client_order_id}, "
            f"IB Order ID: {trade.order.orderId}, "
            f"{position.shares} shares of {position.symbol.symbol}"
        )

        return ib_order

    except (IBConnectionError, IBOrderError) as e:
        logger.error(
            f"Failed to submit IB SELL order for {position.symbol.symbol}: {e}",
            exc_info=True
        )
        return None


def execute_recommendations(
    recommendations: list[Recommendation],
    portfolio: Portfolio,
    trade_date: date,
) -> list[DayTradePosition]:
    """
    Execute trading recommendations.

    If portfolio uses Interactive Brokers:
        - Submits market orders to IB
        - Creates positions with PENDING status
        - Returns immediately (order monitor task handles fills)

    If portfolio uses simulation:
        - Creates transactions immediately
        - Creates positions with OPEN status
        - Returns filled positions
    """
    executed_positions: list[DayTradePosition] = []
    if not recommendations:
        return executed_positions

    # Interactive Brokers mode
    if portfolio.use_interactive_brokers:
        return _execute_recommendations_ib(recommendations, portfolio, trade_date)

    # Simulated mode (original logic)
    return _execute_recommendations_simulated(recommendations, portfolio, trade_date)


def _execute_recommendations_ib(
    recommendations: list[Recommendation],
    portfolio: Portfolio,
    trade_date: date,
) -> list[DayTradePosition]:
    """Execute recommendations via Interactive Brokers"""
    executed_positions: list[DayTradePosition] = []

    try:
        connector = IBConnector(portfolio)
        connector.connect()
    except (IBConnectionError, ValueError) as e:
        logger.error(f"Failed to connect to IB for portfolio {portfolio.id}: {e}")
        return executed_positions

    try:
        for idx, rec in enumerate(recommendations, start=1):
            if rec.symbol.exchange_id != portfolio.exchange_id:
                continue

            # Skip if a position already exists (any status)
            existing_position = DayTradePosition.objects.filter(
                portfolio=portfolio,
                symbol=rec.symbol,
                trade_date=trade_date,
            ).first()
            if existing_position:
                logger.info(
                    f"Skipping {rec.symbol.symbol} - position already exists "
                    f"with status {existing_position.status}"
                )
                continue

            # Quantize shares based on portfolio's fractional flag
            if portfolio.dt_allow_fractional_shares:
                shares = rec.shares.quantize(Decimal("0.0001"))
            else:
                shares = Decimal(str(int(rec.shares)))

            if shares < 1:
                continue

            # Estimate cost (actual will be determined at fill)
            estimated_cost = Decimal(str(rec.entry_price)) * shares

            # Check if enough cash
            if portfolio.cash_balance < estimated_cost:
                logger.info(
                    f"Insufficient cash for {rec.symbol.symbol}: "
                    f"need ${estimated_cost}, have ${portfolio.cash_balance}"
                )
                continue

            # Submit order to IB
            ib_order = _submit_ib_buy_order(
                connector=connector,
                portfolio=portfolio,
                symbol=rec.symbol,
                shares=shares,
                trade_date=trade_date,
                rank=idx
            )

            if not ib_order:
                logger.warning(f"Failed to submit IB order for {rec.symbol.symbol}")
                continue

            # Reserve cash immediately when order is submitted
            # This prevents over-committing cash with multiple pending orders
            portfolio.cash_balance -= estimated_cost
            portfolio.save(update_fields=["cash_balance", "updated_at"])

            logger.info(
                f"Reserved ${estimated_cost} for {rec.symbol.symbol}, "
                f"remaining cash: ${portfolio.cash_balance}"
            )

            # Record recommendation
            _record_recommendation(trade_date, rec, idx)

            # Create position with PENDING status
            # Position will be updated to OPEN when order fills
            position = DayTradePosition.objects.create(
                portfolio=portfolio,
                symbol=rec.symbol,
                trade_date=trade_date,
                status=DayTradePositionStatus.PENDING,
                shares=shares,
                allocation=rec.allocation,
                entry_price=Decimal(str(rec.entry_price)),  # Will be updated with actual fill price
                entry_time=dj_timezone.now(),
                target_price=Decimal(str(rec.target_price)).quantize(Decimal("0.01")),
                stop_price=Decimal(str(rec.stop_price)).quantize(Decimal("0.01")),
                confidence_score=rec.confidence_score,
                predicted_return=rec.predicted_return,
                recommendation_rank=idx,
                notes=f"IB Order ID: {ib_order.ib_order_id}, Client Order ID: {ib_order.client_order_id}"
            )

            # Link order to position
            ib_order.day_trade_position = position
            ib_order.save(update_fields=["day_trade_position"])

            executed_positions.append(position)
            logger.info(
                f"Created PENDING position for {rec.symbol.symbol}, "
                f"IB Order ID: {ib_order.ib_order_id}"
            )

    finally:
        connector.disconnect()

    return executed_positions


def _execute_recommendations_simulated(
    recommendations: list[Recommendation],
    portfolio: Portfolio,
    trade_date: date,
) -> list[DayTradePosition]:
    """Execute recommendations in simulation mode (original logic)"""
    executed_positions: list[DayTradePosition] = []

    with transaction.atomic():
        for idx, rec in enumerate(recommendations, start=1):
            if rec.symbol.exchange_id != portfolio.exchange_id:
                continue

            # Skip if an open position already exists for this symbol/trade date
            existing_position = DayTradePosition.objects.filter(
                portfolio=portfolio,
                symbol=rec.symbol,
                trade_date=trade_date,
                status=DayTradePositionStatus.OPEN,
            ).first()
            if existing_position:
                continue

            live_price = fetch_live_price(rec.symbol)
            base_price = Decimal(str(live_price if live_price else rec.entry_price))

            # Apply transaction costs (commission + slippage)
            commission_cost = Decimal(str(COMMISSION_PER_SHARE)) * rec.shares
            slippage_cost = base_price * Decimal(str(SLIPPAGE_BPS / 10000.0))
            entry_price = base_price + slippage_cost

            # Quantize shares based on portfolio's fractional flag
            if portfolio.dt_allow_fractional_shares:
                shares = rec.shares.quantize(Decimal("0.0001"))  # 4 decimal places for fractional
            else:
                shares = Decimal(str(int(rec.shares)))  # Whole shares only

            total_cost = (entry_price * shares) + commission_cost

            # Check if enough cash (including transaction costs)
            if portfolio.cash_balance < total_cost:
                continue

            rec.symbol.latest_price = entry_price.quantize(Decimal("0.01"))
            rec.symbol.price_updated_at = dj_timezone.now()
            rec.symbol.save(update_fields=["latest_price", "price_updated_at"])

            _create_transaction(
                portfolio=portfolio,
                symbol=rec.symbol,
                quantity=shares,
                price=entry_price.quantize(Decimal("0.01")),
                transaction_date=trade_date,
                notes=f"Autonomous intraday entry rank {idx}",
            )

            _record_recommendation(trade_date, rec, idx)

            position = DayTradePosition.objects.create(
                portfolio=portfolio,
                symbol=rec.symbol,
                trade_date=trade_date,
                status=DayTradePositionStatus.OPEN,
                shares=shares,
                allocation=rec.allocation,
                entry_price=entry_price,
                entry_time=dj_timezone.now(),
                target_price=Decimal(str(rec.target_price)).quantize(Decimal("0.01")),
                stop_price=Decimal(str(rec.stop_price)).quantize(Decimal("0.01")),
                confidence_score=rec.confidence_score,
                predicted_return=rec.predicted_return,
                recommendation_rank=idx,
            )
            executed_positions.append(position)

    return executed_positions


def get_open_day_trade_positions(portfolio: Portfolio, trade_date: date | None = None) -> list[DayTradePosition]:
    qs = DayTradePosition.objects.filter(portfolio=portfolio, status=DayTradePositionStatus.OPEN)
    if trade_date:
        qs = qs.filter(trade_date=trade_date)
    return list(qs.select_related("symbol"))


def close_position(position: DayTradePosition, exit_price: Decimal, reason: str):
    """
    Close a position.

    If portfolio uses IB:
        - Submits SELL market order
        - Updates position to CLOSING status
        - Order monitor task will complete the close when filled

    If simulation:
        - Creates SELL transaction immediately
        - Updates position to CLOSED status
    """
    portfolio = position.portfolio

    # Interactive Brokers mode
    if portfolio.use_interactive_brokers:
        return _close_position_ib(position, reason)

    # Simulated mode
    return _close_position_simulated(position, exit_price, reason)


def _close_position_ib(position: DayTradePosition, reason: str):
    """Close position via Interactive Brokers"""
    portfolio = position.portfolio

    try:
        connector = IBConnector(portfolio)
        connector.connect()

        # Submit SELL order
        ib_order = _submit_ib_sell_order(
            connector=connector,
            portfolio=portfolio,
            position=position,
            exit_reason=reason
        )

        connector.disconnect()

        if not ib_order:
            logger.error(f"Failed to submit IB SELL order for position {position.id}")
            return

        # Update position to CLOSING status
        position.status = DayTradePositionStatus.CLOSING
        position.exit_reason = reason
        position.save(update_fields=["status", "exit_reason", "updated_at"])

        logger.info(
            f"Position {position.id} marked as CLOSING, "
            f"IB Order ID: {ib_order.ib_order_id}"
        )

    except (IBConnectionError, ValueError) as e:
        logger.error(
            f"Failed to close position {position.id} via IB: {e}",
            exc_info=True
        )


def _close_position_simulated(position: DayTradePosition, exit_price: Decimal, reason: str):
    """Close position in simulation mode (original logic)"""
    portfolio = position.portfolio

    with transaction.atomic():
        # Use save() instead of create() to trigger holding updates
        txn = PortfolioTransaction(
            portfolio=portfolio,
            symbol=position.symbol,
            transaction_type=TransactionType.SELL,
            quantity=position.shares,
            price=exit_price.quantize(Decimal("0.01")),
            transaction_date=position.trade_date,
            notes=f"Autonomous intraday exit: {reason}",
        )
        txn.save()

        position.status = DayTradePositionStatus.CLOSED
        position.exit_price = exit_price
        position.exit_time = dj_timezone.now()
        position.exit_reason = reason
        position.save(update_fields=["status", "exit_price", "exit_time", "exit_reason", "updated_at"])


def monitor_positions(portfolio: Portfolio):
    """
    Monitor open positions and close if stop/target is hit.
    Only runs during market hours.
    """
    # Check market hours before fetching prices
    if not is_market_open():
        return

    positions = get_open_day_trade_positions(portfolio)
    for position in positions:
        live_price = fetch_live_price(position.symbol)
        if live_price is None:
            continue
        price = Decimal(str(live_price))
        if price >= position.target_price:
            close_position(position, price, "target_hit")
        elif price <= position.stop_price:
            close_position(position, price, "stop_hit")

    # No re-entry trades during the day; purchases only occur during the morning window


def close_all_positions(portfolio: Portfolio):
    """Close all open positions at end of trading day and create snapshot."""
    positions = get_open_day_trade_positions(portfolio)
    for position in positions:
        live_price = fetch_live_price(position.symbol)
        exit_price = Decimal(str(live_price if live_price else position.entry_price))
        close_position(position, exit_price, "session_close")

    portfolio.refresh_from_db()
    PortfolioSnapshot.objects.update_or_create(
        portfolio=portfolio,
        date=dj_timezone.now().date(),
        defaults={
            "total_value": Decimal(str(portfolio.current_value())),
            "total_invested": Decimal(str(portfolio.total_invested())),
            "gain_loss": Decimal(str(portfolio.total_gain_loss())),
            "gain_loss_percent": Decimal(str(portfolio.total_gain_loss_percent())),
        },
    )
