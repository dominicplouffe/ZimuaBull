from django.core.management.base import BaseCommand

from zimuabull.services.portfolio_review import generate_weekly_portfolio_report


class Command(BaseCommand):
    help = "Generate markdown report summarising weekly portfolio performance."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="Reference date (YYYY-MM-DD). Defaults to today.")

    def handle(self, *args, **options):
        reference_date = options.get("date")
        if reference_date:
            from datetime import datetime

            ref = datetime.strptime(reference_date, "%Y-%m-%d").date()
        else:
            ref = None

        report = generate_weekly_portfolio_report(reference_date=ref)
        self.stdout.write(report)
