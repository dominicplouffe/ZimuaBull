from django.db import models


class DaySymbolChoice(models.TextChoices):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    STRONG_BUY = "STRONG_BUY"
    STRONG_SELL = "STRONG_SELL"
    NA = "NA"


class CloseBucketChoice(models.TextChoices):
    UP = "UP"
    DOWN = "DOWN"
    NA = "NA"


class DayPredictionChoice(models.TextChoices):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"


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

    last_open = models.FloatField()
    last_close = models.FloatField()
    last_volume = models.IntegerField()
    obv_status = models.CharField(
        max_length=20, choices=DaySymbolChoice.choices, default=DaySymbolChoice.NA
    )
    thirty_close_trend = models.FloatField()
    close_bucket = models.CharField(
        max_length=20, choices=CloseBucketChoice.choices, default=CloseBucketChoice.NA
    )
    accuracy = models.FloatField(null=True, blank=True)
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


class DayPrediction(models.Model):
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    date = models.DateField()
    buy_price = models.FloatField()
    sell_price = models.FloatField()
    diff = models.FloatField()
    prediction = models.CharField(
        max_length=20,
        choices=DayPredictionChoice.choices,
        default=DayPredictionChoice.NEUTRAL,
    )
    buy_date = models.DateField(null=True, blank=True)
    sell_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{} - {}".format(self.symbol, self.date)

    unique_together = ("symbol", "date")


class Favorite(models.Model):
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "{} - {}".format(self.symbol, self.user)

    unique_together = ("symbol", "user")
