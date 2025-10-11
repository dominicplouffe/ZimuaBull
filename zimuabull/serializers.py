from rest_framework import serializers

from .models import (
    DayPrediction,
    DaySymbol,
    Exchange,
    Favorite,
    News,
    NewsSentiment,
    Portfolio,
    PortfolioHolding,
    Symbol,
    SymbolNews,
)


class ExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exchange
        fields = "__all__"


class SymbolSerializer(serializers.ModelSerializer):
    exchange = ExchangeSerializer(read_only=True)

    class Meta:
        model = Symbol
        fields = "__all__"


class DaySymbolSerializer(serializers.ModelSerializer):
    symbol = SymbolSerializer()

    class Meta:
        model = DaySymbol
        fields = "__all__"


class DaySymbolDetailSerializer(serializers.ModelSerializer):
    """Day symbol data without nested symbol info for lightweight embedding"""

    class Meta:
        model = DaySymbol
        exclude = ["symbol"]


class DayPredictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DayPrediction
        fields = "__all__"


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = "__all__"


class PortfolioHoldingSerializer(serializers.ModelSerializer):
    """Serializer for portfolio holdings (now derived from transactions)"""
    symbol = SymbolSerializer(read_only=True)
    cost_basis = serializers.SerializerMethodField()
    current_value = serializers.SerializerMethodField()
    gain_loss = serializers.SerializerMethodField()
    gain_loss_percent = serializers.SerializerMethodField()
    days_held = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()
    average_cost = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    stop_loss_price = serializers.SerializerMethodField()
    target_price = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioHolding
        fields = [
            "id", "portfolio", "symbol", "quantity",
            "average_cost", "first_purchase_date", "status",
            "stop_loss_price", "target_price",
            "cost_basis", "current_value", "current_price",
            "gain_loss", "gain_loss_percent", "days_held",
            "created_at", "updated_at"
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_average_cost(self, obj):
        return float(obj.average_cost)

    def get_quantity(self, obj):
        return float(obj.quantity)

    def get_stop_loss_price(self, obj):
        return float(obj.stop_loss_price) if obj.stop_loss_price else None

    def get_target_price(self, obj):
        return float(obj.target_price) if obj.target_price else None

    def get_cost_basis(self, obj):
        return obj.cost_basis()

    def get_current_value(self, obj):
        return obj.current_value()

    def get_gain_loss(self, obj):
        return obj.gain_loss()

    def get_gain_loss_percent(self, obj):
        return round(obj.gain_loss_percent(), 2)

    def get_days_held(self, obj):
        """Calculate days held since first purchase"""
        from datetime import date
        return (date.today() - obj.first_purchase_date).days

    def get_current_price(self, obj):
        # Use latest_price if available, otherwise fall back to last_close
        return float(obj.symbol.latest_price) if obj.symbol.latest_price else float(obj.symbol.last_close)


# PortfolioHoldingCreateSerializer removed - use PortfolioTransaction API instead


class PortfolioSerializer(serializers.ModelSerializer):
    holdings = PortfolioHoldingSerializer(many=True, read_only=True)
    cash_balance = serializers.SerializerMethodField()
    total_invested = serializers.SerializerMethodField()
    current_value = serializers.SerializerMethodField()
    total_gain_loss = serializers.SerializerMethodField()
    total_gain_loss_percent = serializers.SerializerMethodField()
    holdings_count = serializers.SerializerMethodField()
    active_holdings_count = serializers.SerializerMethodField()

    class Meta:
        model = Portfolio
        fields = [
            "id", "name", "description", "user", "exchange",
            "is_active", "created_at", "updated_at",
            "cash_balance", "holdings", "holdings_count", "active_holdings_count",
            "total_invested", "current_value", "total_gain_loss", "total_gain_loss_percent"
        ]
        read_only_fields = ["user", "created_at", "updated_at"]

    def get_cash_balance(self, obj):
        return float(obj.cash_balance)

    def get_total_invested(self, obj):
        return float(obj.total_invested())

    def get_current_value(self, obj):
        return float(obj.current_value())

    def get_total_gain_loss(self, obj):
        return float(obj.total_gain_loss())

    def get_total_gain_loss_percent(self, obj):
        return round(obj.total_gain_loss_percent(), 2)

    def get_holdings_count(self, obj):
        return obj.holdings.count()

    def get_active_holdings_count(self, obj):
        return obj.holdings.filter(status="ACTIVE").count()


class PortfolioSummarySerializer(serializers.ModelSerializer):
    """Lighter serializer for list views without holdings"""
    cash_balance = serializers.SerializerMethodField()
    total_invested = serializers.SerializerMethodField()
    current_value = serializers.SerializerMethodField()
    total_gain_loss = serializers.SerializerMethodField()
    total_gain_loss_percent = serializers.SerializerMethodField()
    holdings_count = serializers.SerializerMethodField()
    active_holdings_count = serializers.SerializerMethodField()

    class Meta:
        model = Portfolio
        fields = [
            "id", "name", "description", "exchange",
            "is_active", "created_at", "updated_at",
            "cash_balance", "holdings_count", "active_holdings_count",
            "total_invested", "current_value", "total_gain_loss", "total_gain_loss_percent"
        ]

    def get_cash_balance(self, obj):
        return float(obj.cash_balance)

    def get_total_invested(self, obj):
        return float(obj.total_invested())

    def get_current_value(self, obj):
        return float(obj.current_value())

    def get_total_gain_loss(self, obj):
        return float(obj.total_gain_loss())

    def get_total_gain_loss_percent(self, obj):
        return round(obj.total_gain_loss_percent(), 2)

    def get_holdings_count(self, obj):
        return obj.holdings.count()

    def get_active_holdings_count(self, obj):
        return obj.holdings.filter(status="ACTIVE").count()


class NewsSentimentSerializer(serializers.ModelSerializer):
    """Serializer for news sentiment analysis results"""

    class Meta:
        model = NewsSentiment
        fields = [
            "sentiment_score",
            "justification",
            "description",
            "model_name",
            "analyzed_at",
        ]


class NewsSerializer(serializers.ModelSerializer):
    """Serializer for news articles with optional sentiment"""
    sentiment = NewsSentimentSerializer(read_only=True)
    symbols = serializers.SerializerMethodField()

    class Meta:
        model = News
        fields = [
            "id",
            "url",
            "title",
            "snippet",
            "source",
            "published_date",
            "thumbnail_url",
            "sentiment",
            "symbols",
            "created_at",
        ]

    def get_symbols(self, obj):
        """Return list of symbol tickers mentioned in this news"""
        symbol_news = SymbolNews.objects.filter(news=obj).select_related("symbol")
        return [
            {
                "symbol": sn.symbol.symbol,
                "exchange": sn.symbol.exchange.code,
                "is_primary": sn.is_primary,
            }
            for sn in symbol_news
        ]


class NewsListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for news list views (without full sentiment details)"""
    sentiment_score = serializers.SerializerMethodField()
    symbol_count = serializers.SerializerMethodField()

    class Meta:
        model = News
        fields = [
            "id",
            "url",
            "title",
            "snippet",
            "source",
            "published_date",
            "thumbnail_url",
            "sentiment_score",
            "symbol_count",
            "created_at",
        ]

    def get_sentiment_score(self, obj):
        """Return just the sentiment score if available"""
        if hasattr(obj, "sentiment"):
            return obj.sentiment.sentiment_score
        return None

    def get_symbol_count(self, obj):
        """Return count of symbols mentioned in this news"""
        return obj.symbols.count()
