from django.core.management.base import BaseCommand
from django.db import transaction

import yfinance as yf

from zimuabull.models import Portfolio, PortfolioHolding
from zimuabull.tasks.portfolio_price_update import is_market_open


def resolve_tsx_ticker(symbol, exchange_code):
    """
    Specialized function for resolving Toronto Stock Exchange (TSX) tickers

    Handles different ticker variations for Canadian stocks
    """
    # If exchange is TSX, always append .TO
    if exchange_code == "TSE":
        return f"{symbol}.TO"

    return symbol  # For other exchanges, return as-is

class Command(BaseCommand):
    help = "Test portfolio price updates manually"

    def add_arguments(self, parser):
        parser.add_argument(
            "--exchange",
            type=str,
            help="Specific exchange code to test market status (e.g., TO, NYSE, NASDAQ)"
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Actually update prices in the database"
        )

    def handle(self, *args, **options):
        # Check market status for a specific exchange if provided
        if options.get("exchange"):
            market_open = is_market_open(options["exchange"])
            self.stdout.write(self.style.SUCCESS(
                f"Market status for {options['exchange']}: {'Open' if market_open else 'Closed'}"
            ))

        # Get all portfolios and their holdings
        portfolios = Portfolio.objects.all()

        if not portfolios:
            self.stdout.write(self.style.WARNING("No portfolios found in the database"))
            return

        # Track overall results
        total_symbols = 0
        symbols_updated = 0
        update_errors = 0

        # Iterate through portfolios
        for portfolio in portfolios:
            self.stdout.write(self.style.NOTICE(f"\nPortfolio: {portfolio.name}"))

            # Get holdings for this portfolio
            holdings = PortfolioHolding.objects.filter(portfolio=portfolio)

            if not holdings:
                self.stdout.write(self.style.WARNING(f"  No holdings found for portfolio {portfolio.name}"))
                continue

            # Iterate through holdings
            for holding in holdings:
                total_symbols += 1
                symbol = holding.symbol
                exchange = symbol.exchange

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

                    # Display symbol and current price
                    if latest_price is not None:
                        self.stdout.write(self.style.SUCCESS(
                            f"  Symbol: {symbol.symbol} ({exchange.code}) - Ticker: {full_ticker} - Current Price: ${latest_price:.2f}"
                        ))

                        # Update prices if --update flag is set
                        if options.get("update"):
                            with transaction.atomic():
                                holding.current_price = latest_price
                                holding.total_value = holding.quantity * latest_price
                                holding.save()
                                symbols_updated += 1
                                self.stdout.write(self.style.SUCCESS(
                                    f"    Updated database for {symbol.symbol}"
                                ))
                    else:
                        self.stdout.write(self.style.ERROR(
                            f"  Could not retrieve price for {symbol.symbol} ({exchange.code}) - Ticker: {full_ticker}"
                        ))
                        update_errors += 1

                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f"  Error processing {symbol.symbol}: {e}"
                    ))
                    update_errors += 1

        # Summary
        self.stdout.write("\n" + self.style.SUCCESS("="*50))
        self.stdout.write(self.style.SUCCESS(f"Total Symbols Processed: {total_symbols}"))
        if options.get("update"):
            self.stdout.write(self.style.SUCCESS(f"Symbols Updated: {symbols_updated}"))
            self.stdout.write(self.style.ERROR(f"Update Errors: {update_errors}"))
