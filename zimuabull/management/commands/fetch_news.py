"""
Django management command to fetch news for symbols using yfinance.

Usage:
  # Fetch news for a specific symbol
  python manage.py fetch_news --symbol AAPL --exchange NASDAQ

  # Fetch news for all active symbols
  python manage.py fetch_news --all

  # Fetch news for symbols with recent activity (default: last 7 days)
  python manage.py fetch_news --active-symbols

  # Fetch news and trigger sentiment analysis
  python manage.py fetch_news --symbol AAPL --exchange NASDAQ --analyze
"""

import logging
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

import yfinance as yf

from zimuabull.models import News, Symbol, SymbolNews

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch news for symbols using Yahoo Finance API"

    def add_arguments(self, parser):
        parser.add_argument(
            "--symbol",
            type=str,
            help="Symbol ticker (requires --exchange)"
        )
        parser.add_argument(
            "--exchange",
            type=str,
            help="Exchange code (e.g., NASDAQ, TSE)"
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Fetch news for all symbols in database"
        )
        parser.add_argument(
            "--active-symbols",
            action="store_true",
            help="Fetch news for symbols with recent updates (last 7 days)"
        )
        parser.add_argument(
            "--max-symbols",
            type=int,
            default=100,
            help="Maximum number of symbols to process (for --all or --active-symbols)"
        )
        parser.add_argument(
            "--analyze",
            action="store_true",
            help="Trigger sentiment analysis after fetching news"
        )

    def handle(self, *args, **options):
        symbol_ticker = options.get("symbol")
        exchange_code = options.get("exchange")
        fetch_all = options.get("all")
        active_symbols = options.get("active_symbols")
        max_symbols = options.get("max_symbols")
        analyze = options.get("analyze")

        # Determine which symbols to fetch news for
        symbols_to_fetch = []

        if symbol_ticker and exchange_code:
            # Fetch for a specific symbol
            try:
                symbol = Symbol.objects.get(symbol=symbol_ticker, exchange__code=exchange_code)
                symbols_to_fetch = [symbol]
            except Symbol.DoesNotExist:
                raise CommandError(f"Symbol {symbol_ticker}:{exchange_code} not found")

        elif fetch_all:
            # Fetch for all symbols
            symbols_to_fetch = list(Symbol.objects.all()[:max_symbols])
            self.stdout.write(f"Fetching news for {len(symbols_to_fetch)} symbols (max: {max_symbols})")

        elif active_symbols:
            # Fetch for symbols with recent activity
            from datetime import timedelta
            from django.utils import timezone as tz
            cutoff_date = tz.now() - timedelta(days=7)
            symbols_to_fetch = list(
                Symbol.objects.filter(updated_at__gte=cutoff_date).order_by("-updated_at")[:max_symbols]
            )
            self.stdout.write(f"Fetching news for {len(symbols_to_fetch)} active symbols (last 7 days)")

        else:
            raise CommandError(
                "Must specify either --symbol and --exchange, --all, or --active-symbols"
            )

        # Fetch news for each symbol
        total_fetched = 0
        total_new = 0
        symbols_processed = 0

        for symbol in symbols_to_fetch:
            try:
                fetched, new = self._fetch_news_for_symbol(symbol)
                total_fetched += fetched
                total_new += new
                symbols_processed += 1

                self.stdout.write(
                    f"  {symbol.symbol}:{symbol.exchange.code} - Fetched {fetched} articles ({new} new)"
                )

            except Exception as e:
                logger.exception(f"Error fetching news for {symbol.symbol}: {e}")
                self.stdout.write(
                    self.style.ERROR(f"  {symbol.symbol}:{symbol.exchange.code} - Error: {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted: Processed {symbols_processed} symbols, "
                f"fetched {total_fetched} articles ({total_new} new)"
            )
        )

        # Trigger sentiment analysis if requested
        if analyze:
            print("HERE")
            self.stdout.write("\nTriggering sentiment analysis for new articles...")
            from zimuabull.tasks.news_sentiment import analyze_news_sentiment
            analyze_news_sentiment()

    def _fetch_news_for_symbol(self, symbol):
        """
        Fetch news for a single symbol using yfinance.
        Returns (total_fetched, total_new) tuple.
        """
        # Get Yahoo Finance ticker
        yf_ticker = self._get_yf_ticker(symbol)

        try:
            ticker = yf.Ticker(yf_ticker)
            news_items = ticker.news

            if not news_items:
                return 0, 0

            fetched = 0
            new = 0

            for item in news_items:
                try:
                    news_obj, created = self._save_news_item(item, symbol)
                    fetched += 1
                    if created:
                        new += 1
                except Exception as e:
                    logger.warning(f"Failed to save news item: {e}")
                    continue

            return fetched, new

        except Exception as e:
            logger.error(f"Failed to fetch news for {symbol.symbol}: {e}")
            raise

    def _get_yf_ticker(self, symbol):
        """Get the Yahoo Finance ticker string for a symbol."""
        exchange_code = symbol.exchange.code

        # Special handling for TSX (Toronto Stock Exchange)
        if exchange_code in ["TSE", "TO"]:
            return f"{symbol.symbol}.TO"

        # Add more exchange-specific handling as needed
        # NYSE, NASDAQ, etc. typically work without suffix
        return symbol.symbol

    def _save_news_item(self, item, symbol):
        """
        Save a news item to the database with deduplication.
        Returns (news_obj, created) tuple.
        """
        # Handle both old and new yfinance news structures
        content = item.get("content", {})

        # Try to get URL from multiple possible locations
        url = None
        if "canonicalUrl" in content and isinstance(content["canonicalUrl"], dict):
            url = content["canonicalUrl"].get("url")
        if not url and "clickThroughUrl" in content and isinstance(content["clickThroughUrl"], dict):
            url = content["clickThroughUrl"].get("url")
        if not url:
            url = item.get("link")

        if not url:
            raise ValueError("News item missing URL")

        # Get title from content or top level
        title = content.get("title") or item.get("title", "")
        title = title[:500]

        # Get snippet/summary
        snippet = content.get("summary") or content.get("description") or item.get("summary", "")

        # Get publisher info
        provider = content.get("provider", {})
        if isinstance(provider, dict):
            source = provider.get("displayName", "Yahoo Finance")
        else:
            source = item.get("publisher", "Yahoo Finance")

        # Get thumbnail
        thumbnail_url = None
        thumbnail = content.get("thumbnail") or item.get("thumbnail")
        if thumbnail:
            if isinstance(thumbnail, dict):
                resolutions = thumbnail.get("resolutions", [])
                if resolutions and isinstance(resolutions, list):
                    # Get the largest resolution
                    thumbnail_url = resolutions[0].get("url")
            elif isinstance(thumbnail, list) and thumbnail:
                thumbnail_url = thumbnail[0].get("url")

        # Parse published date
        published_date = None

        # Try new format first (ISO string)
        pub_date_str = content.get("pubDate") or content.get("displayTime")
        if pub_date_str:
            try:
                from dateutil import parser
                published_date = parser.parse(pub_date_str)
            except Exception:
                pass

        # Try old format (timestamp)
        if not published_date and "providerPublishTime" in item:
            try:
                published_date = datetime.fromtimestamp(
                    item["providerPublishTime"],
                    tz=timezone.utc
                )
            except (ValueError, TypeError):
                pass

        # Use get_or_create with URL as unique key
        with transaction.atomic():
            news_obj, created = News.objects.get_or_create(
                url=url,
                defaults={
                    "title": title,
                    "snippet": snippet,
                    "source": source,
                    "published_date": published_date,
                    "thumbnail_url": thumbnail_url,
                }
            )

            # Create the SymbolNews relationship if it doesn't exist
            SymbolNews.objects.get_or_create(
                symbol=symbol,
                news=news_obj,
                defaults={"is_primary": True}
            )

        return news_obj, created
