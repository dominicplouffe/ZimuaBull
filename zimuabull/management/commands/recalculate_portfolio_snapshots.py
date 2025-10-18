"""
Management command to recalculate all daily portfolio snapshots based on transactions.

This command rebuilds the PortfolioSnapshot records by:
1. Identifying all dates where transactions occurred for each portfolio
2. For each date, calculating the portfolio value at end-of-day based on:
   - All transactions up to and including that date
   - Historical prices for holdings on that date
3. Creating or updating PortfolioSnapshot records

Usage:
    python manage.py recalculate_portfolio_snapshots
    python manage.py recalculate_portfolio_snapshots --portfolio 15
    python manage.py recalculate_portfolio_snapshots --start-date 2025-01-01
    python manage.py recalculate_portfolio_snapshots --force  # Recalculate existing snapshots
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.db.models import Min, Max

from zimuabull.models import (
    Portfolio,
    PortfolioSnapshot,
    PortfolioTransaction,
    PortfolioHolding,
    DaySymbol,
)
from zimuabull.services.portfolio_risk import upsert_portfolio_risk_metrics


class Command(BaseCommand):
    help = "Recalculate all daily portfolio snapshots based on transaction history"

    def add_arguments(self, parser):
        parser.add_argument(
            "--portfolio",
            type=int,
            help="Recalculate for specific portfolio ID only",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="Start date for recalculation (YYYY-MM-DD). Defaults to first transaction date.",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            help="End date for recalculation (YYYY-MM-DD). Defaults to today.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recalculate even if snapshot already exists (will update existing records)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )

    def handle(self, *args, **options):
        portfolio_id = options.get("portfolio")
        start_date_str = options.get("start_date")
        end_date_str = options.get("end_date")
        force = options.get("force", False)
        dry_run = options.get("dry_run", False)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made\n"))

        # Get portfolios to process
        if portfolio_id:
            try:
                portfolios = Portfolio.objects.filter(id=portfolio_id)
                if not portfolios.exists():
                    self.stdout.write(self.style.ERROR(f"Portfolio {portfolio_id} not found"))
                    return
            except Portfolio.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Portfolio {portfolio_id} not found"))
                return
        else:
            portfolios = Portfolio.objects.all()

        # Parse dates
        if start_date_str:
            try:
                start_date = date.fromisoformat(start_date_str)
            except ValueError:
                self.stdout.write(self.style.ERROR(f"Invalid start date format: {start_date_str}. Use YYYY-MM-DD"))
                return
        else:
            start_date = None

        if end_date_str:
            try:
                end_date = date.fromisoformat(end_date_str)
            except ValueError:
                self.stdout.write(self.style.ERROR(f"Invalid end date format: {end_date_str}. Use YYYY-MM-DD"))
                return
        else:
            end_date = date.today()

        self.stdout.write(f"Processing {portfolios.count()} portfolio(s)...\n")

        total_snapshots_created = 0
        total_snapshots_updated = 0
        total_snapshots_skipped = 0

        for idx, portfolio in enumerate(portfolios, 1):
            self.stdout.write(f"\n[{idx}/{portfolios.count()}] Processing: {portfolio.name} (ID: {portfolio.id})")
            self.stdout.write("-" * 80)

            # Get date range for this portfolio
            txn_dates = PortfolioTransaction.objects.filter(
                portfolio=portfolio
            ).aggregate(
                first=Min('transaction_date'),
                last=Max('transaction_date')
            )

            portfolio_start_date = txn_dates['first']
            portfolio_end_date = txn_dates['last']

            if not portfolio_start_date:
                self.stdout.write(self.style.WARNING(f"  No transactions found for {portfolio.name}. Skipping."))
                continue

            # Apply user-specified date range
            if start_date and start_date > portfolio_start_date:
                portfolio_start_date = start_date

            if portfolio_end_date > end_date:
                portfolio_end_date = end_date

            self.stdout.write(f"  Date range: {portfolio_start_date} to {portfolio_end_date}")

            # Process each date
            current_date = portfolio_start_date
            snapshots_created = 0
            snapshots_updated = 0
            snapshots_skipped = 0

            while current_date <= portfolio_end_date:
                # Check if snapshot already exists
                existing_snapshot = PortfolioSnapshot.objects.filter(
                    portfolio=portfolio,
                    date=current_date
                ).first()

                if existing_snapshot and not force:
                    snapshots_skipped += 1
                    current_date += timedelta(days=1)
                    continue

                # Calculate portfolio value for this date
                snapshot_data = self._calculate_portfolio_value_at_date(
                    portfolio,
                    current_date
                )

                if snapshot_data is None:
                    # No data for this date (no transactions or holdings)
                    current_date += timedelta(days=1)
                    continue

                if not dry_run:
                    with db_transaction.atomic():
                        if existing_snapshot:
                            # Update existing
                            existing_snapshot.total_value = snapshot_data['total_value']
                            existing_snapshot.total_invested = snapshot_data['total_invested']
                            existing_snapshot.gain_loss = snapshot_data['gain_loss']
                            existing_snapshot.gain_loss_percent = snapshot_data['gain_loss_percent']
                            existing_snapshot.save()
                            snapshots_updated += 1
                        else:
                            # Create new
                            PortfolioSnapshot.objects.create(
                                portfolio=portfolio,
                                date=current_date,
                                total_value=snapshot_data['total_value'],
                                total_invested=snapshot_data['total_invested'],
                                gain_loss=snapshot_data['gain_loss'],
                                gain_loss_percent=snapshot_data['gain_loss_percent']
                            )
                            snapshots_created += 1

                        try:
                            upsert_portfolio_risk_metrics(portfolio, current_date)
                        except Exception as exc:  # pragma: no cover - console output
                            self.stdout.write(
                                self.style.WARNING(
                                    f"    Warning: failed to compute risk metrics for {portfolio.name} on {current_date}: {exc}"
                                )
                            )
                else:
                    # Dry run - just count
                    if existing_snapshot:
                        snapshots_updated += 1
                    else:
                        snapshots_created += 1

                current_date += timedelta(days=1)

            # Summary for this portfolio
            self.stdout.write(self.style.SUCCESS(
                f"  Created: {snapshots_created}, Updated: {snapshots_updated}, Skipped: {snapshots_skipped}"
            ))

            total_snapshots_created += snapshots_created
            total_snapshots_updated += snapshots_updated
            total_snapshots_skipped += snapshots_skipped

        # Final summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write("=" * 80)
        self.stdout.write(f"Portfolios processed: {portfolios.count()}")
        self.stdout.write(f"Snapshots created: {total_snapshots_created}")
        self.stdout.write(f"Snapshots updated: {total_snapshots_updated}")
        self.stdout.write(f"Snapshots skipped: {total_snapshots_skipped}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN - No changes were made"))
        else:
            self.stdout.write(self.style.SUCCESS("\nRecalculation completed successfully!"))

    def _calculate_portfolio_value_at_date(self, portfolio, snapshot_date):
        """
        Calculate the portfolio value at a specific date based on transaction history.

        Returns dict with:
        - total_value: cash + market value of holdings
        - total_invested: market value of holdings
        - gain_loss: unrealized + realized gains
        - gain_loss_percent: percentage gain/loss
        """
        # Get all transactions up to and including this date
        transactions = PortfolioTransaction.objects.filter(
            portfolio=portfolio,
            transaction_date__lte=snapshot_date
        ).order_by('transaction_date', 'created_at')

        if not transactions.exists():
            return None

        # Calculate cash balance
        cash_balance = Decimal('0')
        holdings = {}  # symbol_id -> {'quantity': Decimal, 'avg_cost': Decimal}

        for txn in transactions:
            if txn.transaction_type == 'DEPOSIT':
                cash_balance += txn.amount

            elif txn.transaction_type == 'WITHDRAWAL':
                cash_balance -= txn.amount

            elif txn.transaction_type == 'BUY' and txn.symbol:
                symbol_id = txn.symbol_id
                amount = txn.quantity * txn.price
                cash_balance -= amount

                if symbol_id not in holdings:
                    holdings[symbol_id] = {
                        'symbol': txn.symbol,
                        'quantity': Decimal('0'),
                        'total_cost': Decimal('0')
                    }

                holdings[symbol_id]['quantity'] += txn.quantity
                holdings[symbol_id]['total_cost'] += amount

            elif txn.transaction_type == 'SELL' and txn.symbol:
                symbol_id = txn.symbol_id
                amount = txn.quantity * txn.price
                cash_balance += amount

                if symbol_id in holdings:
                    # Calculate cost of shares sold
                    if holdings[symbol_id]['quantity'] > 0:
                        cost_per_share = holdings[symbol_id]['total_cost'] / holdings[symbol_id]['quantity']
                        cost_sold = cost_per_share * txn.quantity

                        holdings[symbol_id]['quantity'] -= txn.quantity
                        holdings[symbol_id]['total_cost'] -= cost_sold

                        # Remove if fully sold
                        if holdings[symbol_id]['quantity'] <= 0:
                            del holdings[symbol_id]

        # Calculate market value of holdings at the snapshot date
        total_holdings_value = Decimal('0')
        total_holdings_cost = Decimal('0')

        for symbol_id, holding_data in holdings.items():
            if holding_data['quantity'] <= 0:
                continue

            symbol = holding_data['symbol']
            quantity = holding_data['quantity']
            total_cost = holding_data['total_cost']

            # Get historical price for this date
            historical_price = self._get_symbol_price_at_date(symbol, snapshot_date)

            if historical_price:
                market_value = quantity * historical_price
                total_holdings_value += market_value
                total_holdings_cost += total_cost

        # Calculate totals
        total_value = cash_balance + total_holdings_value
        total_invested = total_holdings_value
        gain_loss = total_holdings_value - total_holdings_cost

        # Calculate percentage
        if total_holdings_cost > 0:
            gain_loss_percent = (gain_loss / total_holdings_cost) * 100
        else:
            gain_loss_percent = Decimal('0')

        return {
            'total_value': total_value,
            'total_invested': total_invested,
            'gain_loss': gain_loss,
            'gain_loss_percent': gain_loss_percent
        }

    def _get_symbol_price_at_date(self, symbol, target_date):
        """
        Get the closing price for a symbol on a specific date.
        Falls back to the most recent price before that date if exact date not found.
        """
        # Try exact date first
        day_symbol = DaySymbol.objects.filter(
            symbol=symbol,
            date=target_date
        ).first()

        if day_symbol:
            return Decimal(str(day_symbol.close))

        # Fall back to most recent price before target date
        day_symbol = DaySymbol.objects.filter(
            symbol=symbol,
            date__lt=target_date
        ).order_by('-date').first()

        if day_symbol:
            return Decimal(str(day_symbol.close))

        # Last resort: use symbol's last_close
        if symbol.last_close:
            return Decimal(str(symbol.last_close))

        return None
