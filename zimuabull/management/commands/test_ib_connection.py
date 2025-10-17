"""
Management command to test Interactive Brokers connection for a portfolio.
"""
from django.core.management.base import BaseCommand

from zimuabull.daytrading.ib_connector import validate_ib_configuration
from zimuabull.models import Portfolio


class Command(BaseCommand):
    help = "Test Interactive Brokers connection for a portfolio"

    def add_arguments(self, parser):
        parser.add_argument(
            "portfolio_id",
            type=int,
            help="Portfolio ID to test"
        )

    def handle(self, *args, **options):
        portfolio_id = options["portfolio_id"]

        try:
            portfolio = Portfolio.objects.get(id=portfolio_id)
        except Portfolio.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Portfolio {portfolio_id} not found")
            )
            return

        self.stdout.write(f"\nTesting IB connection for portfolio: {portfolio.name}")
        self.stdout.write(f"User: {portfolio.user.username}")
        self.stdout.write(f"Exchange: {portfolio.exchange.code}")
        self.stdout.write("")

        # Display configuration
        self.stdout.write("Configuration:")
        self.stdout.write(f"  use_interactive_brokers: {portfolio.use_interactive_brokers}")
        self.stdout.write(f"  ib_host: {portfolio.ib_host}")
        self.stdout.write(f"  ib_port: {portfolio.ib_port}")
        self.stdout.write(f"  ib_client_id: {portfolio.ib_client_id}")
        self.stdout.write(f"  ib_account: {portfolio.ib_account or '(default)'}")
        self.stdout.write(f"  ib_is_paper: {portfolio.ib_is_paper}")
        self.stdout.write("")

        # Validate configuration
        self.stdout.write("Testing connection...")
        is_valid, message = validate_ib_configuration(portfolio)

        if is_valid:
            self.stdout.write(
                self.style.SUCCESS(f"✓ Connection successful: {message}")
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"✗ Connection failed: {message}")
            )
            self.stdout.write("")
            self.stdout.write("Troubleshooting tips:")
            self.stdout.write("1. Ensure IB Gateway or TWS is running")
            self.stdout.write("2. Check API settings in IB Gateway/TWS:")
            self.stdout.write("   - Enable API connections")
            self.stdout.write("   - Add 127.0.0.1 to trusted IPs (or your host IP)")
            self.stdout.write("   - Check port number matches")
            self.stdout.write("3. Verify client_id is unique (not in use by another connection)")
            self.stdout.write("4. Check firewall settings")
