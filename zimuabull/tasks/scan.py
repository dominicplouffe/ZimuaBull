from zimuabull.scanners import tse
from zimuabull.tasks.download_symbols import download_tse
from celery import shared_task


@shared_task(ignore_result=True, queue="pidashtasks")
def scan():
    download_tse()

    t = tse.TSEScanner()
    t.scan()
