from zimuabull.models import Exchange

from .tse import BaseScanner


class NASDAQScanner(BaseScanner):
    def __init__(self):
        exchange = Exchange.objects.get(code="NASDAQ")
        super().__init__(exchange)
