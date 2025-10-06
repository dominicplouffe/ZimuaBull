from zimuabull.models import Exchange
from .tse import BaseScanner


class NYSEScanner(BaseScanner):
    def __init__(self):
        exchange = Exchange.objects.get(code="NYSE")
        super().__init__(exchange)