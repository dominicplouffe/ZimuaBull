import json

from django.core.management.base import BaseCommand

from zimuabull.tasks.portfolio_price_update import market_pulse_update


class Command(BaseCommand):
    help = "Test the market pulse update task (portfolio symbols + market indices)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting market pulse update test..."))
        self.stdout.write("")

        try:
            # Run the task
            result = market_pulse_update()

            # Pretty print the result
            self.stdout.write(self.style.SUCCESS("Task completed successfully!"))
            self.stdout.write("")
            self.stdout.write(json.dumps(result, indent=2))
            self.stdout.write("")

            # Summary
            if result.get("status") == "skipped":
                self.stdout.write(self.style.WARNING(f"Status: {result['reason']}"))
            else:
                portfolio_updates = result.get("portfolio_updates", {})
                index_updates = result.get("index_updates", {})

                self.stdout.write(self.style.SUCCESS("=== SUMMARY ==="))
                self.stdout.write(f"Status: {result.get('status')}")
                self.stdout.write(f"Timestamp: {result.get('timestamp')}")
                self.stdout.write("")
                self.stdout.write("Market Status:")
                for exchange, status in result.get("market_status", {}).items():
                    status_text = "🟢 OPEN" if status else "🔴 CLOSED"
                    self.stdout.write(f"  {exchange}: {status_text}")
                self.stdout.write("")
                self.stdout.write("Portfolio Symbol Updates:")
                self.stdout.write(f"  ✅ Successful: {portfolio_updates.get('successful')}")
                self.stdout.write(f"  ❌ Failed: {portfolio_updates.get('failed')}")
                self.stdout.write("")
                self.stdout.write("Market Index Updates:")
                self.stdout.write(f"  ✅ Successful: {index_updates.get('successful')}")
                self.stdout.write(f"  ❌ Failed: {index_updates.get('failed')}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error running task: {e!s}"))
            raise
