from __future__ import annotations

from datetime import date as dt_date

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from zimuabull.daytrading.feature_builder import build_feature_snapshot
from zimuabull.daytrading.modeling import load_model, prepare_features_for_inference
from zimuabull.models import DaySymbol, FeatureSnapshot, Symbol


class DayTradingPredictor:
    """Reusable predictor that keeps the model in memory between score calls."""

    def __init__(self):
        self.model, self.trained_columns, self.imputer = load_model()

    def predict(
        self,
        symbol_code: str,
        trade_date: dt_date,
        exchange_code: str | None = None,
        overwrite: bool = False,
    ) -> dict:
        symbol_qs = Symbol.objects.filter(symbol=symbol_code.upper())
        if exchange_code:
            symbol_qs = symbol_qs.filter(exchange__code=exchange_code.upper())

        symbol = symbol_qs.first()
        if not symbol:
            if exchange_code:
                raise ValueError(f"Symbol '{symbol_code}' on exchange '{exchange_code}' not found.")
            raise ValueError(f"Symbol '{symbol_code}' not found. Specify --exchange if needed.")

        snapshot = (
            FeatureSnapshot.objects.filter(symbol=symbol, trade_date=trade_date)
            .order_by("-created_at")
            .first()
        )

        if overwrite or snapshot is None:
            snapshot = build_feature_snapshot(symbol, trade_date, overwrite=overwrite)

        if snapshot is None:
            raise ValueError(
                f"Unable to build feature snapshot for {symbol.symbol} on {trade_date}. "
                "Ensure historical data is available."
            )

        features = snapshot.features or {}
        if not features:
            raise ValueError(
                f"Feature snapshot for {symbol.symbol} on {trade_date} is empty. "
                "Regenerate features or check data completeness."
            )

        feature_df = pd.DataFrame([features])
        encoded = prepare_features_for_inference(feature_df, self.trained_columns, self.imputer)
        predicted_return = float(self.model.predict(encoded)[0])

        actual_return: float | None = None
        day_symbol = DaySymbol.objects.filter(symbol=symbol, date=trade_date).first()
        if day_symbol and day_symbol.open:
            actual_return = (float(day_symbol.close) - float(day_symbol.open)) / float(day_symbol.open)

        return {
            "symbol": symbol.symbol,
            "exchange": symbol.exchange.code if symbol.exchange else None,
            "trade_date": trade_date,
            "predicted_return": predicted_return,
            "actual_return": actual_return,
            "snapshot": snapshot,
        }


class Command(BaseCommand):
    help = "Predict the intraday return for a symbol using the latest trained day trading model."

    def add_arguments(self, parser):
        parser.add_argument("symbol", type=str, help="Ticker symbol, e.g., AAPL")
        parser.add_argument(
            "--exchange",
            type=str,
            help="Exchange code (e.g., NASDAQ). Required if multiple symbols share the same ticker.",
        )
        parser.add_argument(
            "--date",
            type=str,
            help="Trade date to score (YYYY-MM-DD). Defaults to today.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Recompute the feature snapshot instead of using the cached version.",
        )

    def handle(self, *args, **options):
        symbol_code: str = options["symbol"].upper()
        exchange_code: str | None = options.get("exchange")
        trade_date_str: str | None = options.get("date")
        overwrite: bool = bool(options.get("overwrite"))

        if trade_date_str:
            try:
                trade_date = dt_date.fromisoformat(trade_date_str)
            except ValueError as exc:  # pragma: no cover - user input validation
                raise CommandError(f"Invalid date format '{trade_date_str}'. Use YYYY-MM-DD.") from exc
        else:
            trade_date = dt_date.today()

        predictor = DayTradingPredictor()
        try:
            result = predictor.predict(
                symbol_code=symbol_code,
                trade_date=trade_date,
                exchange_code=exchange_code,
                overwrite=overwrite,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Prediction complete"))
        self.stdout.write("-" * 60)
        self.stdout.write(f"Symbol:        {result['symbol']}")
        self.stdout.write(f"Exchange:      {result['exchange']}")
        self.stdout.write(f"Trade Date:    {result['trade_date']}")
        self.stdout.write(
            f"Predicted Return (open→close %): {result['predicted_return'] * 100:.4f}%"
        )
        if result.get("actual_return") is not None:
            self.stdout.write(
                f"Actual Return (open→close %):   {result['actual_return'] * 100:.4f}%"
            )
        self.stdout.write("-" * 60)
