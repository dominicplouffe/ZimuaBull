from django.db import models


class DaySymbolChoice(models.TextChoices):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    STRONG_BUY = "STRONG_BUY"
    STRONG_SELL = "STRONG_SELL"
    NA = "NA"


# Create your models here.
class Exchange(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, null=True, blank=True)
    country = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{} - {}".format(self.name, self.country)

    unique_together = ("name", "country")


class Symbol(models.Model):
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{} - {} = {}".format(self.name, self.symbol, self.exchange.name)

    unique_together = ("symbol", "exchange")


class DaySymbol(models.Model):
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    date = models.DateField()
    open = models.FloatField()
    high = models.FloatField()
    low = models.FloatField()
    adj_close = models.FloatField()
    close = models.FloatField()
    volume = models.IntegerField()
    obv = models.BigIntegerField()
    obv_signal = models.IntegerField()
    obv_signal_sum = models.IntegerField()
    price_diff = models.FloatField()
    thirty_price_diff = models.FloatField()
    thirty_close_trend = models.FloatField()
    status = models.CharField(
        max_length=20, choices=DaySymbolChoice.choices, default=DaySymbolChoice.NA
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{} - {}".format(self.symbol, self.date)

    unique_together = ("symbol", "date")
