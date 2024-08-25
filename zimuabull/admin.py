from django.contrib import admin
from .models import Exchange, Symbol, DaySymbol


# Register your models here.
@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "country", "created_at", "updated_at")
    search_fields = ("name", "code", "country")
    list_filter = ("country",)


@admin.register(Symbol)
class SymbolAdmin(admin.ModelAdmin):
    list_display = ("name", "symbol", "exchange", "created_at", "updated_at")
    search_fields = ("name", "symbol", "exchange__name")
    list_filter = ("exchange__country",)


@admin.register(DaySymbol)
class DaySymbolAdmin(admin.ModelAdmin):
    list_display = (
        "symbol",
        "date",
        "open",
        "high",
        "low",
        "adj_close",
        "close",
        "volume",
        "obv",
        "obv_signal",
        "obv_signal_sum",
        "price_diff",
        "thirty_price_diff",
        "thirty_close_trend",
        "status",
        "created_at",
        "updated_at",
    )
    search_fields = ("symbol__name", "date")
    list_filter = ("status",)
