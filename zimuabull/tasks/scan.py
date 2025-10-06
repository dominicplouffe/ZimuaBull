from zimuabull.scanners import tse
from zimuabull.scanners.nasdaq import NASDAQScanner
from zimuabull.scanners.nyse import NYSEScanner
from zimuabull.tasks.download_symbols import download_tse, download_nasdaq, download_nyse
from celery import shared_task


@shared_task(ignore_result=True, queue="pidashtasks")
def scan():
    # Download symbols for all exchanges
    download_tse()
    download_nasdaq()
    download_nyse()

    # Scan TSE
    t = tse.TSEScanner()
    t.scan()

    # Scan NASDAQ
    nasdaq = NASDAQScanner()
    nasdaq.scan()

    # Scan NYSE
    nyse = NYSEScanner()
    nyse.scan()
