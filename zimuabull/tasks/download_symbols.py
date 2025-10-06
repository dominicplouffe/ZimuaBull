import requests
import logging
import time
from zimuabull.models import Symbol, Exchange, DaySymbolChoice, CloseBucketChoice
from lxml import html

logger = logging.getLogger(__name__)

TSE_URL = "https://stockanalysis.com/list/toronto-stock-exchange/"
NASDAQ_URL = "https://stockanalysis.com/list/nasdaq-stocks/"
NYSE_URL = "https://stockanalysis.com/list/nyse-stocks/"

# Rate limiting
REQUEST_DELAY = 1  # seconds between requests


def download_exchange_symbols(url, exchange_name, exchange_code, country):
    """Generic function to download symbols from stockanalysis.com"""
    try:
        logger.info(f"Downloading symbols for {exchange_name}")

        # Rate limiting
        time.sleep(REQUEST_DELAY)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        content = html.fromstring(response.content)

        trs = content.xpath('//tr[contains(@class, "svelte")]')

        exchange, _ = Exchange.objects.get_or_create(
            name=exchange_name, country=country, defaults={"code": exchange_code}
        )
        if exchange.code != exchange_code:
            exchange.code = exchange_code
            exchange.save()

        symbols_created = 0
        for tr in trs:
            tds = tr.xpath(".//td")
            if len(tds) < 3:
                continue

            try:
                symbol_text = tds[1].xpath("./a")[0].text
                name = tds[2].text

                if not symbol_text or not name:
                    continue

                _, created = Symbol.objects.get_or_create(
                    symbol=symbol_text,
                    exchange=exchange,
                    defaults=dict(
                        name=name,
                        last_open=0,
                        last_close=0,
                        last_volume=0,
                        obv_status=DaySymbolChoice.NA,
                        thirty_close_trend=0,
                        close_bucket=CloseBucketChoice.NA,
                    ),
                )
                if created:
                    symbols_created += 1

            except (IndexError, AttributeError) as e:
                logger.warning(f"Error parsing symbol row: {e}")
                continue

        logger.info(f"Created {symbols_created} new symbols for {exchange_name}")

    except Exception as e:
        logger.error(f"Error downloading symbols for {exchange_name}: {e}")


def download_tse():
    response = requests.get(TSE_URL)
    content = html.fromstring(response.content)

    trs = content.xpath('//tr[contains(@class, "svelte")]')

    exchange, _ = Exchange.objects.get_or_create(
        name="Toronto Stock Exchange", country="Canada", defaults={"code": "TSE"}
    )
    if exchange.code != "TSE":
        exchange.code = "TSE"
        exchange.save()

    for tr in trs:
        tds = tr.xpath(".//td")
        if len(tds) < 3:
            continue

        symbol = tds[1].xpath("./a")[0].text
        name = tds[2].text

        symbol = Symbol.objects.get_or_create(
            symbol=symbol,
            exchange=exchange,
            defaults=dict(
                name=name,
                last_open=0,
                last_close=0,
                last_volume=0,
                obv_status=DaySymbolChoice.NA,
                thirty_close_trend=0,
                close_bucket=CloseBucketChoice.NA,
            ),
        )


def download_nasdaq():
    """Download NASDAQ symbols"""
    download_exchange_symbols(
        NASDAQ_URL, "NASDAQ Stock Exchange", "NASDAQ", "United States"
    )


def download_nyse():
    """Download NYSE symbols"""
    download_exchange_symbols(
        NYSE_URL, "New York Stock Exchange", "NYSE", "United States"
    )
