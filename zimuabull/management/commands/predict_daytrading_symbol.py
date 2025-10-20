from __future__ import annotations

from datetime import date as dt_date

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from zimuabull.daytrading.feature_builder import build_feature_snapshot
from zimuabull.daytrading.modeling import load_model, prepare_features_for_inference
from zimuabull.models import DaySymbol, FeatureSnapshot, Symbol


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

        symbol_qs = Symbol.objects.filter(symbol=symbol_code)
        if exchange_code:
            symbol_qs = symbol_qs.filter(exchange__code=exchange_code.upper())

        symbol = symbol_qs.first()
        if not symbol:
            if exchange_code:
                raise CommandError(f"Symbol '{symbol_code}' on exchange '{exchange_code}' not found.")
            raise CommandError(f"Symbol '{symbol_code}' not found. Specify --exchange if needed.")

        snapshot = FeatureSnapshot.objects.filter(
            symbol=symbol,
            trade_date=trade_date,
        ).order_by("-created_at").first()

        if overwrite or snapshot is None:
            snapshot = build_feature_snapshot(symbol, trade_date, overwrite=overwrite)

        if snapshot is None:
            raise CommandError(
                f"Unable to build feature snapshot for {symbol_code} on {trade_date}. "
                "Ensure historical data is available."
            )

        features = snapshot.features or {}
        if not features:
            raise CommandError(
                f"Feature snapshot for {symbol_code} on {trade_date} is empty. "
                "Regenerate features or check data completeness."
            )

        model, trained_columns, imputer = load_model()

        feature_df = pd.DataFrame([features])
        encoded = prepare_features_for_inference(feature_df, trained_columns, imputer)
        predicted_return = float(model.predict(encoded)[0])

        actual_return_pct: str | None = None
        day_symbol = DaySymbol.objects.filter(symbol=symbol, date=trade_date).first()
        if day_symbol:
            open_price = float(day_symbol.open)
            close_price = float(day_symbol.close)
            if open_price:
                actual_return = (close_price - open_price) / open_price
                actual_return_pct = f"{actual_return * 100:.4f}%"

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Prediction complete"))
        self.stdout.write("-" * 60)
        self.stdout.write(f"Symbol:        {symbol.symbol}")
        self.stdout.write(f"Exchange:      {symbol.exchange.code}")
        self.stdout.write(f"Trade Date:    {trade_date}")
        self.stdout.write(f"Predicted Return (open→close %): {predicted_return * 100:.4f}%")
        if actual_return_pct is not None:
            self.stdout.write(f"Actual Return (open→close %):   {actual_return_pct}")
        self.stdout.write("-" * 60)
