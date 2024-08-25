import requests
from zimuabull.models import Symbol, Exchange
from lxml import html

TSE_URL = "https://stockanalysis.com/list/toronto-stock-exchange/"


def download_tse():
    response = requests.get(TSE_URL)
    content = html.fromstring(response.content)

    trs = content.xpath('//tr[@class="svelte-cod2gs"]')

    exchange, _ = Exchange.objects.get_or_create(
        name="Toronto Stock Exchange", country="Canada"
    )

    for tr in trs:
        tds = tr.xpath(".//td")
        if len(tds) < 3:
            continue

        symbol = tds[1].xpath("./a")[0].text
        name = tds[2].text

        symbol = Symbol.objects.get_or_create(
            name=name, symbol=symbol, exchange=exchange
        )
