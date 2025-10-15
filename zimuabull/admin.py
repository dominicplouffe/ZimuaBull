from django.contrib import admin

from .models import DaySymbol, Exchange, Symbol, PortfolioHoldingLog


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


@admin.register(PortfolioHoldingLog)
class PortfolioHoldingLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "operation",
        "portfolio",
        "symbol",
        "transaction_type",
        "transaction_quantity",
        "transaction_price",
        "quantity_before",
        "quantity_after",
        "holding_status",
    )
    list_filter = ("operation", "transaction_type", "holding_status", "portfolio")
    search_fields = ("symbol__symbol", "portfolio__name", "notes")
    readonly_fields = (
        "portfolio",
        "symbol",
        "transaction",
        "operation",
        "quantity_before",
        "average_cost_before",
        "quantity_after",
        "average_cost_after",
        "transaction_type",
        "transaction_quantity",
        "transaction_price",
        "transaction_date",
        "holding_status",
        "notes",
        "created_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        # Logs should only be created by the system
        return False

    def has_delete_permission(self, request, obj=None):
        # Keep logs for debugging - don't allow deletion
        return False
