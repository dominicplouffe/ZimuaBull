from django.contrib import admin

from .models import DaySymbol, Exchange, IBOrder, PortfolioHoldingLog, Symbol


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


@admin.register(IBOrder)
class IBOrderAdmin(admin.ModelAdmin):
    list_display = (
        "client_order_id",
        "portfolio",
        "symbol",
        "action",
        "quantity",
        "status",
        "ib_order_id",
        "filled_price",
        "submitted_at",
        "filled_at",
    )
    list_filter = ("status", "action", "order_type", "portfolio")
    search_fields = ("client_order_id", "ib_order_id", "symbol__symbol", "portfolio__name")
    readonly_fields = (
        "client_order_id",
        "ib_order_id",
        "ib_perm_id",
        "submitted_at",
        "filled_at",
        "last_updated_at",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)

    fieldsets = (
        ("Basic Info", {
            "fields": (
                "portfolio",
                "day_trade_position",
                "symbol",
                "client_order_id",
            )
        }),
        ("Order Details", {
            "fields": (
                "action",
                "order_type",
                "quantity",
                "limit_price",
            )
        }),
        ("IB Info", {
            "fields": (
                "ib_order_id",
                "ib_perm_id",
                "status",
                "status_message",
            )
        }),
        ("Execution", {
            "fields": (
                "submitted_price",
                "filled_price",
                "filled_quantity",
                "remaining_quantity",
                "commission",
            )
        }),
        ("Timestamps", {
            "fields": (
                "submitted_at",
                "filled_at",
                "last_updated_at",
                "created_at",
                "updated_at",
            )
        }),
        ("Errors", {
            "fields": (
                "error_code",
                "error_message",
            )
        }),
    )

    def has_add_permission(self, request):
        # Orders should only be created by the system
        return False
