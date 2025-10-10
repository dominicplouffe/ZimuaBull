from django.core.management.base import BaseCommand, CommandError

from zimuabull.services.portfolio import delete_portfolio


class Command(BaseCommand):
    help = "Delete a portfolio and all related data (holdings, transactions, snapshots, day-trade positions)."

    def add_arguments(self, parser):
        parser.add_argument("portfolio_id", type=int, help="ID of the portfolio to delete")
        parser.add_argument("--user-id", type=int, default=None, help="Optional user id to enforce ownership")

    def handle(self, *args, **options):
        portfolio_id = options["portfolio_id"]
        user_id = options.get("user_id")

        try:
            result = delete_portfolio(portfolio_id, user_id=user_id)
        except Exception as exc:  # pylint: disable=broad-except
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Deleted portfolio {result['portfolio_id']}"))
        for key, value in result.items():
            if key == "portfolio_id":
                continue
            self.stdout.write(f"  {key.replace('_', ' ')}: {value}")
