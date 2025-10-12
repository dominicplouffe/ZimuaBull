import json
import math
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.utils.decorators import method_decorator

from asgiref.sync import sync_to_async
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework import serializers as rest_serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .chat import ChatOrchestrator
from .chat.sse import sse_response
from .daytrading.trading_engine import generate_recommendations
from .models import (
    Conversation,
    ConversationMessage,
    DayPrediction,
    DayPredictionChoice,
    DaySymbol,
    DaySymbolChoice,
    DayTradingRecommendation,
    Exchange,
    Favorite,
    MarketIndex,
    MarketIndexData,
    News,
    NewsSentiment,
    Portfolio,
    PortfolioHolding,
    PortfolioTransaction,
    SignalHistory,
    Symbol,
    SymbolNews,
)
from .serializers import (
    DayPredictionSerializer,
    DaySymbolDetailSerializer,
    DaySymbolSerializer,
    ExchangeSerializer,
    FavoriteSerializer,
    MarketIndexDataListSerializer,
    MarketIndexSerializer,
    NewsListSerializer,
    NewsSerializer,
    PortfolioHoldingSerializer,
    PortfolioSerializer,
    PortfolioSummarySerializer,
    SymbolSerializer,
    SymbolWithRSISerializer,
)


class DaySymbolPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 1000


class PredictionPagination(PageNumberPagination):
    """Pagination for symbols-by-prediction endpoint with smaller default page size"""
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 1000


class ExchangeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Stock Exchange List

    List all available stock exchanges tracked by the system.

    **Key Fields:**
    - `code`: Exchange code (e.g., "TSE", "NASDAQ", "NYSE")
    - `name`: Full exchange name
    - `country`: Country where exchange is located

    **Example:** `/api/exchanges/`
    """
    queryset = Exchange.objects.all()
    serializer_class = ExchangeSerializer



class DaySymbolViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Daily Stock Data (OHLCV + Technical Analysis)

    Historical daily stock data with OHLCV (Open, High, Low, Close, Volume) and calculated technical indicators.

    **Read-only endpoint** - only GET requests are allowed.

    **Key Fields:**
    - `date`: Trading date
    - `open`, `high`, `low`, `close`: Daily price data
    - `volume`: Trading volume
    - `obv`: On-Balance Volume cumulative indicator
    - `obv_signal`: Daily OBV direction (1=up, 0=down)
    - `obv_signal_sum`: Sum of last 3 OBV signals
    - `thirty_close_trend`: 30-day price trendline angle
    - `status`: Trading signal (BUY/SELL/HOLD/NA)

    **Required Parameters (unless fetching by ID):**
    - `symbol__symbol`: Stock symbol (e.g., AAPL)
    - `symbol__exchange__code`: Exchange code (e.g., NASDAQ)

    **Pagination:**
    - Default page size: 30 records
    - To get more records: Add `?page_size=100` (max 1000)
    - To navigate pages: Add `?page=2`

    **Filtering:**
    - By symbol and exchange: `?symbol__symbol=AAPL&symbol__exchange__code=NASDAQ`
    - Order by date: `?ordering=date` or `?ordering=-date`

    **Example:** `/api/day-symbols/?symbol__symbol=AAPL&symbol__exchange__code=NASDAQ&ordering=-date&page_size=100`
    """
    queryset = DaySymbol.objects.all()
    serializer_class = DaySymbolSerializer
    pagination_class = DaySymbolPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["symbol__symbol", "symbol__exchange__code"]
    ordering_fields = ["date"]
    ordering = ["date"]

    def list(self, request, *args, **kwargs):
        # Require symbol and exchange parameters for list endpoint
        symbol = request.query_params.get("symbol__symbol")
        exchange = request.query_params.get("symbol__exchange__code")

        if not symbol or not exchange:
            return Response(
                {"error": "Both 'symbol__symbol' and 'symbol__exchange__code' parameters are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().list(request, *args, **kwargs)


class DayPredictionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Stock Price Movement Predictions

    AI-powered predictions for near-future (5-day) stock price movements.
    Uses multi-indicator scoring system combining momentum, trends, and volume analysis.

    **Read-only endpoint** - only GET requests are allowed.

    **Key Fields:**
    - `date`: Prediction date
    - `prediction`: Predicted movement (POSITIVE/NEGATIVE/NEUTRAL)
    - `buy_price`: Current price at prediction time
    - `sell_price`: Actual price 5 days later
    - `diff`: Price difference (sell_price - buy_price)
    - `buy_date`: Prediction date
    - `sell_date`: Validation date (5 days later)

    **Prediction Logic:**
    - **POSITIVE**: Expected price increase >2% in 5 days
    - **NEGATIVE**: Expected price decrease >2% in 5 days
    - **NEUTRAL**: Expected minimal movement (<2%)

    **Required Parameters (unless fetching by ID):**
    - `symbol__symbol`: Stock symbol (e.g., AAPL)
    - `symbol__exchange__code`: Exchange code (e.g., NASDAQ)

    **Result Limiting:**
    - Default: Returns only the latest record (most recent prediction)
    - To get more records: Add `?limit=100` (e.g., for 100 most recent predictions)
    - Maximum limit: 1000 records

    **Filtering:**
    - By symbol and exchange: `?symbol__symbol=AAPL&symbol__exchange__code=NASDAQ`
    - Order by date: `?ordering=date` or `?ordering=-date`

    **Examples:**
    - Latest prediction: `/api/day-predictions/?symbol__symbol=AAPL&symbol__exchange__code=NASDAQ`
    - Last 100 predictions: `/api/day-predictions/?symbol__symbol=AAPL&symbol__exchange__code=NASDAQ&limit=100&ordering=-date`
    """
    queryset = DayPrediction.objects.all()
    serializer_class = DayPredictionSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["symbol__symbol", "symbol__exchange__code"]
    ordering_fields = ["date"]
    ordering = ["-date"]

    def list(self, request, *args, **kwargs):
        # Require symbol and exchange parameters for list endpoint
        symbol = request.query_params.get("symbol__symbol")
        exchange = request.query_params.get("symbol__exchange__code")

        if not symbol or not exchange:
            return Response(
                {"error": "Both 'symbol__symbol' and 'symbol__exchange__code' parameters are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get the limit parameter, default to 1 (latest record only)
        limit = request.query_params.get("limit", "1")
        try:
            limit = int(limit)
            limit = max(limit, 1)
            limit = min(limit, 1000)
        except (ValueError, TypeError):
            limit = 1

        # Get the filtered queryset
        queryset = self.filter_queryset(self.get_queryset())

        # Apply limit
        queryset = queryset[:limit]

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class FavoriteList(APIView):
    """
    User's Favorite Symbols

    Get list of symbols favorited by the authenticated user.

    **Authentication Required**

    **Returns:** List of favorite objects with symbol and exchange information
    **Example:**
    ```json
    [
        {"symbol": "AAPL", "exchange": "NASDAQ"},
        {"symbol": "GOOGL", "exchange": "NASDAQ"},
        {"symbol": "SHOP", "exchange": "TSE"}
    ]
    ```
    """
    @method_decorator(login_required)
    def get(self, request):
        user = request.user
        if user.is_authenticated:
            latest_day_prefetch = Prefetch(
                "symbol__daysymbol_set",
                queryset=DaySymbol.objects.order_by("-date")[:1],
                to_attr="latest_day_symbols",
            )

            favorites_queryset = (
                Favorite.objects.filter(user=user)
                .select_related("symbol__exchange")
                .prefetch_related(latest_day_prefetch)
            )

            favorites = []
            for favorite in favorites_queryset:
                symbol = favorite.symbol
                latest_day_symbol = None

                prefetched = getattr(symbol, "latest_day_symbols", [])
                if prefetched:
                    latest_day_symbol = prefetched[0]

                favorite_payload = {
                    "symbol": symbol.symbol,
                    "exchange": symbol.exchange.code,
                }

                day_symbol_data = DaySymbolDetailSerializer(latest_day_symbol).data if latest_day_symbol else None

                favorite_payload["day_symbol"] = day_symbol_data
                favorites.append(favorite_payload)

            return Response(favorites, status=status.HTTP_200_OK)
        return Response([], status=status.HTTP_200_OK)


class AddFavorite(APIView):
    """
    Add Symbol to Favorites

    Add a symbol to the authenticated user's favorites list.

    **Authentication Required**

    **Request Body:**
    ```json
    {
        "symbol": "AAPL",
        "exchange": "NASDAQ"
    }
    ```

    **Returns:** Created favorite object
    """
    @method_decorator(login_required)
    def post(self, request):
        user = request.user
        symbol_ticker = request.data.get("symbol")
        exchange_code = request.data.get("exchange")
        symbol = Symbol.objects.get(symbol=symbol_ticker, exchange__code=exchange_code)
        favorite, _ = Favorite.objects.get_or_create(symbol=symbol, user=user)
        serializer = FavoriteSerializer(favorite)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RemoveFavorite(APIView):
    """
    Remove Symbol from Favorites

    Remove a symbol from the authenticated user's favorites list.

    **Authentication Required**

    **Request Body:**
    ```json
    {
        "symbol": "AAPL",
        "exchange": "NASDAQ"
    }
    ```

    **Returns:** Empty response with 204 status
    """
    @method_decorator(login_required)
    def post(self, request):
        user = request.user
        symbol_ticker = request.data.get("symbol")
        exchange_code = request.data.get("exchange")
        symbol = Symbol.objects.get(symbol=symbol_ticker, exchange__code=exchange_code)
        for favorite in Favorite.objects.filter(symbol=symbol, user=user):
            favorite.delete()
        return Response([], status=status.HTTP_204_NO_CONTENT)


class PredictionCountByDate(APIView):
    """
    Count of Predictions by Sentiment for a Given Date

    Returns the count of positive, negative, and neutral predictions for a specific date.

    **Query Parameters:**
    - `date`: Date in YYYY-MM-DD format (required)

    **Returns:**
    ```json
    {
        "date": "2024-01-15",
        "positive": 125,
        "negative": 45,
        "neutral": 30,
        "total": 200
    }
    ```

    **Example:** `/api/prediction-count/?date=2024-01-15`
    """
    def get(self, request):
        date_str = request.query_params.get("date")

        if not date_str:
            return Response(
                {"error": "Date parameter is required (format: YYYY-MM-DD)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            prediction_date = date.fromisoformat(date_str)
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Count predictions by type
        predictions = DayPrediction.objects.filter(date=prediction_date)

        positive_count = predictions.filter(prediction=DayPredictionChoice.POSITIVE).count()
        negative_count = predictions.filter(prediction=DayPredictionChoice.NEGATIVE).count()
        neutral_count = predictions.filter(prediction=DayPredictionChoice.NEUTRAL).count()

        return Response({
            "date": date_str,
            "positive": positive_count,
            "negative": negative_count,
            "neutral": neutral_count,
            "total": positive_count + negative_count + neutral_count
        })


class SymbolsByPrediction(viewsets.ReadOnlyModelViewSet):
    """
    Symbols Filtered by Latest Prediction Type

    Returns symbols filtered by their most recent prediction sentiment (positive, negative, or neutral).

    **Read-only endpoint** - only GET requests are allowed.

    **Required Query Parameters:**
    - `prediction`: Prediction type (POSITIVE, NEGATIVE, or NEUTRAL)

    **Optional Query Parameters:**
    - `exchange`: Filter by exchange code (e.g., NASDAQ, TSE)
    - `obv_status`: Filter by OBV status (BUY, SELL, HOLD, STRONG_BUY, STRONG_SELL, NA)
    - `sector`: Filter by sector (exact match, case-insensitive)
    - `industry`: Filter by industry (exact match, case-insensitive)
    - `symbol`: Search by ticker symbol (substring match, case-insensitive)
    - `rsi_min`: Minimum RSI value (float, e.g., 0-100)
    - `rsi_max`: Maximum RSI value (float, e.g., 0-100)
    - `ordering`: Field to sort by (symbol, last_close, accuracy, thirty_close_trend, latest_rsi)
    - `direction`: Sort direction (asc or desc, default: asc)
    - `page_size`: Number of results per page (default: 10, max: 1000)
    - `page`: Page number

    **Returns:** List of symbols with their latest prediction details and RSI

    **Examples:**
    - All positive predictions: `/api/symbols-by-prediction/?prediction=POSITIVE`
    - NASDAQ positive with RSI > 70: `/api/symbols-by-prediction/?prediction=POSITIVE&exchange=NASDAQ&rsi_min=70`
    - Sorted by RSI descending: `/api/symbols-by-prediction/?prediction=POSITIVE&ordering=latest_rsi&direction=desc`
    - Technology sector strong buys: `/api/symbols-by-prediction/?prediction=POSITIVE&sector=Technology&obv_status=STRONG_BUY`
    """
    serializer_class = SymbolWithRSISerializer
    pagination_class = PredictionPagination
    filter_backends = []  # We'll handle filtering manually for better control

    def get_queryset(self):
        from django.db.models import F, OuterRef, Subquery

        prediction_type = self.request.query_params.get("prediction", "").upper()
        exchange_code = self.request.query_params.get("exchange")
        obv_status = self.request.query_params.get("obv_status", "").upper()
        sector = self.request.query_params.get("sector")
        industry = self.request.query_params.get("industry")
        symbol_search = self.request.query_params.get("symbol")
        rsi_min = self.request.query_params.get("rsi_min")
        rsi_max = self.request.query_params.get("rsi_max")
        ordering_field = self.request.query_params.get("ordering", "symbol")
        direction = self.request.query_params.get("direction", "asc")

        if not prediction_type:
            return Symbol.objects.none()

        if prediction_type not in [DayPredictionChoice.POSITIVE, DayPredictionChoice.NEGATIVE, DayPredictionChoice.NEUTRAL]:
            return Symbol.objects.none()

        # Get the latest prediction for each symbol
        latest_predictions = DayPrediction.objects.filter(
            symbol=OuterRef("pk")
        ).order_by("-date")

        # Get the latest RSI for each symbol (for filtering and sorting)
        latest_rsi_subquery = DaySymbol.objects.filter(
            symbol=OuterRef("pk")
        ).order_by("-date")

        # Get symbols where the latest prediction matches the requested type
        queryset = Symbol.objects.annotate(
            latest_prediction=Subquery(latest_predictions.values("prediction")[:1]),
            latest_prediction_date=Subquery(latest_predictions.values("date")[:1]),
            latest_rsi_value=Subquery(latest_rsi_subquery.values("rsi")[:1])
        ).filter(
            latest_prediction=prediction_type
        ).select_related("exchange")

        # Apply filters
        if exchange_code:
            queryset = queryset.filter(exchange__code=exchange_code)

        if obv_status:
            queryset = queryset.filter(obv_status=obv_status)

        if sector:
            queryset = queryset.filter(sector__iexact=sector)

        if industry:
            queryset = queryset.filter(industry__iexact=industry)

        if symbol_search:
            queryset = queryset.filter(symbol__icontains=symbol_search)

        # RSI filters (using the annotated field)
        if rsi_min is not None:
            try:
                rsi_min_float = float(rsi_min)
                queryset = queryset.filter(latest_rsi_value__gte=rsi_min_float)
            except ValueError:
                pass  # Ignore invalid rsi_min

        if rsi_max is not None:
            try:
                rsi_max_float = float(rsi_max)
                queryset = queryset.filter(latest_rsi_value__lte=rsi_max_float)
            except ValueError:
                pass  # Ignore invalid rsi_max

        # Apply sorting
        valid_ordering_fields = {
            "symbol": "symbol",
            "last_close": "last_close",
            "accuracy": "accuracy",
            "thirty_close_trend": "thirty_close_trend",
            "latest_rsi": "latest_rsi_value"  # Use the annotated field
        }

        if ordering_field in valid_ordering_fields:
            db_field = valid_ordering_fields[ordering_field]
            if direction == "desc":
                queryset = queryset.order_by(F(db_field).desc(nulls_last=True))
            else:
                queryset = queryset.order_by(F(db_field).asc(nulls_last=True))
        else:
            # Default ordering
            queryset = queryset.order_by("symbol")

        return queryset

    def list(self, request, *args, **kwargs):
        prediction_type = request.query_params.get("prediction", "").upper()

        if not prediction_type:
            return Response(
                {"error": "Prediction parameter is required (POSITIVE, NEGATIVE, or NEUTRAL)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if prediction_type not in [DayPredictionChoice.POSITIVE, DayPredictionChoice.NEGATIVE, DayPredictionChoice.NEUTRAL]:
            return Response(
                {"error": "Invalid prediction type. Must be POSITIVE, NEGATIVE, or NEUTRAL"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().list(request, *args, **kwargs)


class DaySymbolChoiceCount(APIView):
    """
    Count of Symbols by Day Symbol Status

    Returns the count of symbols by their current status (BUY, SELL, HOLD, STRONG_BUY, STRONG_SELL, NA).

    **Returns:**
    ```json
    {
        "BUY": 25,
        "SELL": 10,
        "HOLD": 50,
        "STRONG_BUY": 5,
        "STRONG_SELL": 2,
        "NA": 108,
        "total": 200
    }
    ```

    **Example:** `/api/symbol-status-count/`
    """
    def get(self, request):
        # Count symbols by their obv_status field
        counts = Symbol.objects.values("obv_status").annotate(count=Count("id"))

        result = {
            "BUY": 0,
            "SELL": 0,
            "HOLD": 0,
            "STRONG_BUY": 0,
            "STRONG_SELL": 0,
            "NA": 0
        }

        total = 0
        for item in counts:
            status_value = item["obv_status"]
            count_value = item["count"]
            if status_value in result:
                result[status_value] = count_value
            total += count_value

        result["total"] = total
        return Response(result)


class SymbolsByStatus(viewsets.ReadOnlyModelViewSet):
    """
    Symbols Filtered by Day Symbol Status

    Returns symbols filtered by their current status (BUY, SELL, HOLD, STRONG_BUY, STRONG_SELL, NA).

    **Read-only endpoint** - only GET requests are allowed.

    **Required Query Parameters:**
    - `status`: Status type (BUY, SELL, HOLD, STRONG_BUY, STRONG_SELL, or NA)

    **Optional Query Parameters:**
    - `exchange`: Filter by exchange code (e.g., NASDAQ, TSE)
    - `page_size`: Number of results per page (default: 30, max: 1000)
    - `page`: Page number

    **Returns:** List of symbols with the specified status

    **Examples:**
    - All BUY signals: `/api/symbols-by-status/?status=BUY`
    - NASDAQ BUY signals: `/api/symbols-by-status/?status=BUY&exchange=NASDAQ`
    - First 100 results: `/api/symbols-by-status/?status=STRONG_BUY&page_size=100`
    """
    serializer_class = SymbolSerializer
    pagination_class = DaySymbolPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["symbol", "name"]
    ordering = ["symbol"]

    def get_queryset(self):
        status_type = self.request.query_params.get("status", "").upper()
        exchange_code = self.request.query_params.get("exchange")

        if not status_type:
            return Symbol.objects.none()

        valid_statuses = [choice[0] for choice in DaySymbolChoice.choices]
        if status_type not in valid_statuses:
            return Symbol.objects.none()

        queryset = Symbol.objects.filter(obv_status=status_type).select_related("exchange")

        if exchange_code:
            queryset = queryset.filter(exchange__code=exchange_code)

        return queryset

    def list(self, request, *args, **kwargs):
        status_type = request.query_params.get("status", "").upper()

        if not status_type:
            return Response(
                {"error": "Status parameter is required (BUY, SELL, HOLD, STRONG_BUY, STRONG_SELL, or NA)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        valid_statuses = [choice[0] for choice in DaySymbolChoice.choices]
        if status_type not in valid_statuses:
            return Response(
                {"error": f"Invalid status type. Must be one of: {', '.join(valid_statuses)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().list(request, *args, **kwargs)


class PortfolioViewSet(viewsets.ModelViewSet):
    """
    Portfolio Management

    Create and manage investment portfolios to track stock holdings.

    **Authentication Required**

    **Key Features:**
    - Create multiple portfolios per user
    - Track holdings with purchase price and date
    - Monitor daily gains/losses
    - Exchange-restricted portfolios (all holdings must be from same exchange)

    **Endpoints:**
    - `GET /api/portfolios/` - List user's portfolios
    - `POST /api/portfolios/` - Create new portfolio
    - `GET /api/portfolios/{id}/` - Get portfolio details with all holdings
    - `PUT/PATCH /api/portfolios/{id}/` - Update portfolio
    - `DELETE /api/portfolios/{id}/` - Delete portfolio

    **Example Create:**
    ```json
    {
        "name": "Tech Growth Portfolio",
        "description": "Long-term tech investments",
        "exchange": 1,
        "initial_balance": 10000
    }
    ```
    """
    permission_classes = [IsAuthenticated]
    pagination_class = DaySymbolPagination

    def get_queryset(self):
        return Portfolio.objects.filter(user=self.request.user).prefetch_related("holdings__symbol__exchange")

    def get_serializer_class(self):
        from .serializers_transactions import PortfolioWithCashSerializer
        if self.action == "list":
            return PortfolioSummarySerializer
        if self.action in ["create", "update", "partial_update"]:
            return PortfolioWithCashSerializer
        return PortfolioSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PortfolioHoldingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Portfolio Holdings - READ ONLY

    View current holdings within portfolios.
    Holdings are automatically calculated from transactions.

    **Use /api/transactions/ to BUY or SELL stocks**

    **Authentication Required**

    **Key Features:**
    - View current holdings derived from transaction history
    - Track average cost basis
    - Track performance per holding
    - Update stop loss and target prices

    **Endpoints:**
    - `GET /api/holdings/` - List all user's holdings (filterable by portfolio)
    - `GET /api/holdings/{id}/` - Get holding details
    - `PATCH /api/holdings/{id}/` - Update stop loss/target price only

    **Query Parameters:**
    - `portfolio`: Filter by portfolio ID
    - `status`: Filter by status (ACTIVE)
    - `symbol`: Filter by symbol ID

    **To add/sell holdings, use /api/transactions/**
    """
    permission_classes = [IsAuthenticated]
    pagination_class = DaySymbolPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["portfolio", "status", "symbol"]
    ordering_fields = ["first_purchase_date", "quantity"]
    ordering = ["-first_purchase_date"]
    serializer_class = PortfolioHoldingSerializer

    def get_queryset(self):
        return PortfolioHolding.objects.filter(
            portfolio__user=self.request.user
        ).select_related("portfolio", "symbol__exchange")

    def partial_update(self, request, *args, **kwargs):
        """Allow updating stop_loss_price and target_price only"""
        # Only allow updating these fields
        allowed_fields = ["stop_loss_price", "target_price"]
        for key in request.data:
            if key not in allowed_fields:
                return Response(
                    {"error": f"Cannot update field '{key}'. Only stop_loss_price and target_price can be updated. Use /api/transactions/ to buy/sell."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return super().partial_update(request, *args, **kwargs)

    # Removed sell() action - use /api/transactions/ with transaction_type='SELL' instead


class PortfolioSummary(APIView):
    """
    Portfolio Summary Across All User Portfolios

    Get aggregated statistics across all user's portfolios.

    **Authentication Required**

    **Returns:**
    ```json
    {
        "total_portfolios": 3,
        "active_portfolios": 2,
        "total_invested": 50000.00,
        "total_current_value": 55000.00,
        "total_gain_loss": 5000.00,
        "total_gain_loss_percent": 10.00,
        "total_holdings": 25,
        "portfolios": [...]
    }
    ```

    **Example:** `/api/portfolio-summary/`
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        portfolios = Portfolio.objects.filter(user=request.user)

        total_invested = sum(p.total_invested() for p in portfolios)
        total_current_value = sum(p.current_value() for p in portfolios)
        total_gain_loss = total_current_value - total_invested
        total_gain_loss_percent = (total_gain_loss / total_invested * 100) if total_invested > 0 else 0

        total_holdings = sum(p.holdings.filter(status="ACTIVE").count() for p in portfolios)

        portfolio_summaries = PortfolioSummarySerializer(portfolios, many=True).data

        return Response({
            "total_portfolios": portfolios.count(),
            "active_portfolios": portfolios.filter(is_active=True).count(),
            "total_invested": float(total_invested),
            "total_current_value": float(total_current_value),
            "total_gain_loss": float(total_gain_loss),
            "total_gain_loss_percent": round(total_gain_loss_percent, 2),
            "total_holdings": total_holdings,
            "portfolios": portfolio_summaries
        })



class SignalExplanation(APIView):
    """
    Get Trading Signal Explanation

    Get detailed explanation of why a symbol has its current trading signal.

    **URL Parameters:**
    - `symbol`: Stock symbol (e.g., AAPL)
    - `exchange`: Exchange code (e.g., NASDAQ)

    **Returns:**
    ```json
    {
        "symbol": "AAPL",
        "exchange": "NASDAQ",
        "signal": "BUY",
        "prediction": "POSITIVE",
        "obv_signal_sum": 2,
        "trend_angle": 12.5,
        "price_bucket": "UP",
        "accuracy": 0.75,
        "explanation": "Prediction: POSITIVE | OBV Signal Sum: 2 | 30-day Trend: 12.50° | Price Bucket: UP | Accuracy: 75.0%"
    }
    ```

    **Example:** `/api/signal-explanation/?symbol=AAPL&exchange=NASDAQ`
    """

    def get(self, request):
        symbol_ticker = request.query_params.get("symbol")
        exchange_code = request.query_params.get("exchange")

        if not symbol_ticker or not exchange_code:
            return Response(
                {"error": "Both 'symbol' and 'exchange' parameters are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            symbol = Symbol.objects.get(symbol=symbol_ticker, exchange__code=exchange_code)
        except Symbol.DoesNotExist:
            return Response(
                {"error": f"Symbol {symbol_ticker} not found on exchange {exchange_code}"},
                status=status.HTTP_404_NOT_FOUND
            )

        explanation_data = symbol.get_signal_explanation()
        explanation_data["symbol"] = symbol.symbol
        explanation_data["exchange"] = symbol.exchange.code

        return Response(explanation_data)


class SymbolSearch(viewsets.ReadOnlyModelViewSet):
    """
    Search Symbols by Ticker or Name

    Search for symbols by partial match on ticker symbol or company name.
    Returns matching symbols with their current metrics.

    **Read-only endpoint** - only GET requests are allowed.

    **Required Query Parameters:**
    - `q` or `query`: Search term (minimum 1 character)

    **Optional Query Parameters:**
    - `exchange`: Filter by exchange code (e.g., TSE, NASDAQ, NYSE)
    - `page_size`: Number of results per page (default: 30, max: 100)

    **Search Behavior:**
    - Searches both symbol ticker and company name
    - Case-insensitive partial matching
    - Results ordered by: exact ticker match first, then alphabetically

    **Returns:**
    Each result includes:
    - Symbol details (ticker, name, exchange)
    - Current price metrics (last_open, last_close, last_volume)
    - Technical indicators (obv_status, thirty_close_trend, close_bucket)
    - Prediction accuracy

    **Examples:**
    - Search by ticker: `/api/symbol-search/?q=AAPL`
    - Search by partial name: `/api/symbol-search/?q=apple`
    - Filter by exchange: `/api/symbol-search/?q=bank&exchange=TSE`
    - Limit results: `/api/symbol-search/?q=tech&page_size=10`
    """
    serializer_class = SymbolSerializer
    pagination_class = DaySymbolPagination

    def get_queryset(self):
        query = self.request.query_params.get("q") or self.request.query_params.get("query")
        exchange_code = self.request.query_params.get("exchange")

        if not query:
            return Symbol.objects.none()

        # Search by symbol (ticker) or name
        queryset = Symbol.objects.filter(
            Q(symbol__icontains=query) | Q(name__icontains=query)
        ).select_related("exchange")

        # Filter by exchange if provided
        if exchange_code:
            queryset = queryset.filter(exchange__code=exchange_code)

        # Order by: exact ticker matches first, then alphabetically
        from django.db.models import Case, IntegerField, Value, When
        return queryset.annotate(
            exact_match=Case(
                When(symbol__iexact=query, then=Value(0)),
                When(symbol__istartswith=query, then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            )
        ).order_by("exact_match", "symbol")


    def list(self, request, *args, **kwargs):
        query = request.query_params.get("q") or request.query_params.get("query")

        if not query:
            return Response(
                {"error": "Search query parameter 'q' or 'query' is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(query) < 1:
            return Response(
                {"error": "Search query must be at least 1 character"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Override page_size max for search
        page_size = request.query_params.get("page_size")
        if page_size:
            try:
                page_size_int = int(page_size)
                if page_size_int > 100:
                    return Response(
                        {"error": "Maximum page_size is 100 for search results"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except ValueError:
                pass

        return super().list(request, *args, **kwargs)


class LLMContext(APIView):
    """
    Get LLM-Formatted Context Data

    Returns stock market data formatted for LLM consumption (Claude, ChatGPT, etc.).
    Provides natural language summaries and structured data.

    **Query Parameters:**
    - `symbol`: Stock symbol (requires `exchange`)
    - `exchange`: Exchange code
    - `include_history`: Set to "true" to include historical prices (enables moving averages, etc.)
    - `history_days`: Number of days of history (default: 30, max: 365)
    - `portfolio_ids`: Comma-separated portfolio IDs (e.g., "1,2,3")
    - `include_market_overview`: Set to "true" to include market overview
    - `exchange_filter`: Exchange code for market overview

    **Examples:**
    - Symbol with history: `/api/llm-context/?symbol=AAPL&exchange=NASDAQ&include_history=true&history_days=50`
    - Portfolio context: `/api/llm-context/?portfolio_ids=1,2`
    - Market overview: `/api/llm-context/?include_market_overview=true&exchange_filter=TSE`
    - Combined: `/api/llm-context/?symbol=AAPL&exchange=NASDAQ&include_history=true&portfolio_ids=1`
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .llm_helpers import (
            build_system_prompt,
            format_market_overview_for_llm,
            format_portfolio_for_llm,
            format_symbol_for_llm,
        )

        context = {
            "system_prompt": build_system_prompt(),
            "data": {}
        }

        # Symbol data
        symbol_ticker = request.query_params.get("symbol")
        exchange_code = request.query_params.get("exchange")
        include_history = request.query_params.get("include_history") == "true"
        history_days = int(request.query_params.get("history_days", 30))

        if symbol_ticker and exchange_code:
            try:
                symbol = Symbol.objects.get(symbol=symbol_ticker, exchange__code=exchange_code)
                context["data"]["symbol"] = format_symbol_for_llm(
                    symbol,
                    include_history=include_history,
                    history_days=history_days
                )
            except Symbol.DoesNotExist:
                context["data"]["symbol"] = {"error": f"Symbol {symbol_ticker} not found on {exchange_code}"}

        # Portfolio data
        portfolio_ids_str = request.query_params.get("portfolio_ids")
        if portfolio_ids_str:
            try:
                portfolio_ids = [int(pid) for pid in portfolio_ids_str.split(",")]
                portfolios = Portfolio.objects.filter(user=request.user, id__in=portfolio_ids)
                context["data"]["portfolios"] = [format_portfolio_for_llm(p) for p in portfolios]
            except (ValueError, TypeError):
                context["data"]["portfolios"] = {"error": "Invalid portfolio_ids format"}

        # Market overview
        if request.query_params.get("include_market_overview") == "true":
            exchange_filter = request.query_params.get("exchange_filter")
            context["data"]["market_overview"] = format_market_overview_for_llm(exchange_filter)

        return Response(context)


class ChatWithLLM(APIView):
    """
    Conversational Analytics Agent

    Accepts a user prompt, routes it through the orchestration layer (OpenAI +
    structured tools), and responds with natural language plus machine-readable
    analysis for the front-end.

    **Authentication Required**

    **POST Body:**
    ```json
    {
        "message": "How is MSFT trading today?",
        "conversation_id": 42,          // optional, continue existing thread
        "context": {
            "symbol": "MSFT",          // optional hint
            "exchange": "NASDAQ",      // optional, recommended with symbol
            "history_days": 60,         // optional (default 30)
            "include_history": true,    // include time series in analysis block
            "include_portfolio": true   // include user portfolio snapshot
        }
    }
    ```

    **Response:**
    ```json
    {
        "conversation_id": 42,
        "reply": "Here is what I found...",
        "analysis": {
            "symbols": [
                {
                    "symbol": "MSFT",
                    "exchange": "NASDAQ",
                    "name": "Microsoft Corporation",
                    "stats": {
                        "latest_close": 328.45,
                        "change_percent": 0.85,
                        "signal": "BUY",
                        ...
                    },
                    "price_history": [{"date": "2025-10-01", "close": 325.11, ...}]
                }
            ],
            "portfolios": [
                {
                    "portfolio": "TSE Momentum",
                    "exchange": "TSE",
                    "cash_balance": 12000.0,
                    "current_value": 48210.5,
                    "active_positions": 7
                }
            ]
        },
        "messages": [
            {"role": "user", "content": "How is MSFT trading today?"},
            {"role": "assistant", "content": "Here is what I found..."}
        ]
    }
    ```

    The agent stores both user and assistant turns, letting the UI load full
    transcripts via `/api/conversations/` endpoints.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = request.data.get("message")
        conversation_id = request.data.get("conversation_id")
        context_params = request.data.get("context", {})

        if not message:
            return Response(
                {"error": "Message is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create conversation
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id, user=request.user)
            except Conversation.DoesNotExist:
                return Response(
                    {"error": "Conversation not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            conversation = Conversation.objects.create(
                user=request.user,
                title=message[:100]  # Use first message as title
            )

        # Save user message
        ConversationMessage.objects.create(
            conversation=conversation,
            role="user",
            content=message,
            context_data=context_params
        )

        try:
            orchestrator = ChatOrchestrator()
        except RuntimeError as exc:
            fallback_reply = "The analytics engine is not configured. Please contact support."
            ConversationMessage.objects.create(
                conversation=conversation,
                role="assistant",
                content=fallback_reply,
                context_data={"error": str(exc)}
            )
            history = [
                {
                    "role": msg.role,
                    "content": msg.content
                }
                for msg in conversation.messages.order_by("created_at")
            ]
            return Response(
                {
                    "conversation_id": conversation.id,
                    "reply": fallback_reply,
                    "analysis": {},
                    "messages": history,
                    "status_updates": [],
                    "tool_results": [],
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        agent_output = orchestrator.run(request.user, conversation, message, context_params)

        reply = agent_output.get("reply", "I could not generate a response.")
        analysis = agent_output.get("analysis", {})
        status_updates = agent_output.get("status_updates", [])
        tool_results = agent_output.get("tool_results", [])

        ConversationMessage.objects.create(
            conversation=conversation,
            role="assistant",
            content=reply,
            context_data={
                "analysis": analysis,
                "status_updates": status_updates,
                "tool_results": tool_results,
            }
        )

        history = [
            {
                "role": msg.role,
                "content": msg.content
            }
            for msg in conversation.messages.order_by("created_at")
        ]

        return Response({
            "conversation_id": conversation.id,
            "reply": reply,
            "analysis": analysis,
            "messages": history,
            "status_updates": status_updates,
            "tool_results": tool_results,
        })


class SaveChatResponse(APIView):
    """
    Save External Chat Response (Optional)

    Kept for backwards compatibility. Integrations that still call an external LLM
    can push the assistant message into the transcript via this endpoint. Newer
    flows can rely entirely on POST /api/chat/.

    **Authentication Required**

    **POST Body:**
    ```json
    {
        "conversation_id": 1,
        "response": "Based on your portfolio analysis..."
    }
    ```
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        conversation_id = request.data.get("conversation_id")
        response = request.data.get("response")

        if not conversation_id or not response:
            return Response(
                {"error": "conversation_id and response are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            conversation = Conversation.objects.get(id=conversation_id, user=request.user)
        except Conversation.DoesNotExist:
            return Response(
                {"error": "Conversation not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Save assistant response
        ConversationMessage.objects.create(
            conversation=conversation,
            role="assistant",
            content=response
        )

        return Response({
            "success": True,
            "conversation_id": conversation.id,
            "message_count": conversation.messages.count()
        })


async def chat_stream(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)

    message = request.GET.get("message")
    if not message:
        return JsonResponse({"error": "Message is required"}, status=400)

    context_param = request.GET.get("context")
    context = {}
    if context_param:
        try:
            context = json.loads(context_param)
        except json.JSONDecodeError:
            return JsonResponse({"error": "context must be valid JSON"}, status=400)

    conversation_id = request.GET.get("conversation_id")

    if conversation_id:
        try:
            conversation = await sync_to_async(Conversation.objects.get)(id=conversation_id, user=request.user)
        except Conversation.DoesNotExist:
            return JsonResponse({"error": "Conversation not found"}, status=404)
    else:
        conversation = await sync_to_async(Conversation.objects.create)(
            user=request.user,
            title=message[:100]
        )

    await sync_to_async(ConversationMessage.objects.create)(
        conversation=conversation,
        role="user",
        content=message,
        context_data=context
    )

    try:
        orchestrator = ChatOrchestrator()
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=503)

    return sse_response(orchestrator, request.user, conversation, message, context)


class ConversationList(APIView):
    """
    List User's Conversations

    Get all conversations for the authenticated user.

    **Authentication Required**

    **Returns:**
    ```json
    [
        {
            "id": 1,
            "title": "Portfolio analysis",
            "message_count": 5,
            "created_at": "2025-01-07T10:00:00Z",
            "updated_at": "2025-01-07T10:30:00Z"
        }
    ]
    ```
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = Conversation.objects.filter(user=request.user)

        data = []
        for conv in conversations:
            data.append({
                "id": conv.id,
                "title": conv.title,
                "message_count": conv.messages.count(),
                "created_at": conv.created_at,
                "updated_at": conv.updated_at
            })

        return Response(data)

    def delete(self, request):
        conversations = Conversation.objects.filter(user=request.user)
        count = conversations.count()
        conversations.delete()
        return Response({"deleted": count}, status=status.HTTP_200_OK)


class ConversationDetail(APIView):
    """
    Get Conversation History

    Retrieve full conversation history with all messages.

    **Authentication Required**

    **Returns:**
    ```json
    {
        "id": 1,
        "title": "Portfolio analysis",
        "messages": [
            {
                "role": "user",
                "content": "What stocks should I buy?",
                "created_at": "2025-01-07T10:00:00Z"
            },
            {
                "role": "assistant",
                "content": "Based on current market...",
                "created_at": "2025-01-07T10:00:05Z"
            }
        ]
    }
    ```
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        try:
            conversation = Conversation.objects.get(id=conversation_id, user=request.user)
        except Conversation.DoesNotExist:
            return Response(
                {"error": "Conversation not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        messages = []
        for msg in conversation.messages.order_by("created_at"):
            messages.append({
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at
            })

        return Response({
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
            "messages": messages
        })

    def delete(self, request, conversation_id):
        try:
            conversation = Conversation.objects.get(id=conversation_id, user=request.user)
        except Conversation.DoesNotExist:
            return Response(
                {"error": "Conversation not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        conversation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CompareSymbols(APIView):
    """
    Compare Multiple Symbols Side-by-Side

    Compare 2-10 symbols across key metrics for LLM analysis.

    **Query Parameters:**
    - `symbols`: Comma-separated list of "SYMBOL:EXCHANGE" pairs (e.g., "AAPL:NASDAQ,MSFT:NASDAQ,GOOGL:NASDAQ")
    - `include_history`: Set to "true" to include price history (default: false)
    - `history_days`: Days of history if include_history=true (default: 30)

    **Returns:**
    ```json
    {
        "comparison_summary": "Comparing 3 symbols: AAPL (BUY, $178.25), MSFT (HOLD, $370.50)...",
        "symbols": [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "current_price": 178.25,
                "signal": "BUY",
                "sector": "Technology",
                ...
            }
        ],
        "comparative_analysis": {
            "highest_price": {"symbol": "MSFT", "price": 370.50},
            "strongest_signal": ["AAPL"],
            "best_performer_30d": {"symbol": "NVDA", "change_percent": 15.3},
            "sector_breakdown": {"Technology": 3}
        }
    }
    ```

    **Examples:**
    - `/api/compare-symbols/?symbols=AAPL:NASDAQ,MSFT:NASDAQ,GOOGL:NASDAQ`
    - `/api/compare-symbols/?symbols=AAPL:NASDAQ,MSFT:NASDAQ&include_history=true&history_days=50`
    """

    def get(self, request):
        from .llm_helpers import format_symbol_for_llm

        symbols_param = request.query_params.get("symbols")
        include_history = request.query_params.get("include_history") == "true"
        history_days = int(request.query_params.get("history_days", 30))

        if not symbols_param:
            return Response(
                {"error": "symbols parameter is required (format: SYMBOL:EXCHANGE,SYMBOL:EXCHANGE)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse symbols
        symbol_pairs = []
        for pair in symbols_param.split(","):
            parts = pair.strip().split(":")
            if len(parts) != 2:
                return Response(
                    {"error": f"Invalid format for '{pair}'. Use SYMBOL:EXCHANGE"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            symbol_pairs.append((parts[0].upper(), parts[1].upper()))

        if len(symbol_pairs) > 10:
            return Response(
                {"error": "Maximum 10 symbols can be compared at once"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch and format symbols
        symbols_data = []
        for symbol_ticker, exchange_code in symbol_pairs:
            try:
                symbol = Symbol.objects.get(symbol=symbol_ticker, exchange__code=exchange_code)
                symbol_data = format_symbol_for_llm(symbol, include_history=include_history, history_days=history_days)
                symbols_data.append(symbol_data)
            except Symbol.DoesNotExist:
                symbols_data.append({
                    "symbol": symbol_ticker,
                    "exchange": exchange_code,
                    "error": "Not found"
                })

        # Build comparison summary
        valid_symbols = [s for s in symbols_data if "error" not in s]

        if not valid_symbols:
            return Response({
                "error": "None of the requested symbols were found",
                "symbols": symbols_data
            }, status=status.HTTP_404_NOT_FOUND)

        # Comparative analysis
        signal_ranking = {"STRONG_BUY": 5, "BUY": 4, "HOLD": 3, "SELL": 2, "STRONG_SELL": 1, "NA": 0}

        # Find strongest and weakest signals
        all_signals = [s["signal"] for s in valid_symbols]
        strongest_signal_value = max(signal_ranking.get(sig, 0) for sig in all_signals)
        weakest_signal_value = min(signal_ranking.get(sig, 0) for sig in all_signals)

        comparative_analysis = {
            "highest_price": max(valid_symbols, key=lambda s: s["current_price"]),
            "lowest_price": min(valid_symbols, key=lambda s: s["current_price"]),
            "strongest_signal": [s["symbol"] for s in valid_symbols if signal_ranking.get(s["signal"], 0) == strongest_signal_value],
            "weakest_signal": [s["symbol"] for s in valid_symbols if signal_ranking.get(s["signal"], 0) == weakest_signal_value],
            "steepest_uptrend": max(valid_symbols, key=lambda s: s["trend_angle"]) if valid_symbols else None,
            "steepest_downtrend": min(valid_symbols, key=lambda s: s["trend_angle"]) if valid_symbols else None,
        }

        # Sector breakdown
        sectors = {}
        for s in valid_symbols:
            sector = s.get("sector", "Unknown")
            sectors[sector] = sectors.get(sector, 0) + 1
        comparative_analysis["sector_breakdown"] = sectors

        # Performance comparison (if history included)
        if include_history:
            performance = []
            for s in valid_symbols:
                if "price_statistics" in s:
                    performance.append({
                        "symbol": s["symbol"],
                        "change_percent": s["price_statistics"]["change_percent"]
                    })
            if performance:
                performance.sort(key=lambda x: x["change_percent"], reverse=True)
                comparative_analysis["performance_ranking"] = performance
                comparative_analysis["best_performer"] = performance[0] if performance else None
                comparative_analysis["worst_performer"] = performance[-1] if performance else None

        # Summary
        summary_parts = [f"Comparing {len(valid_symbols)} symbols:"]
        for s in valid_symbols[:3]:  # First 3 for summary
            summary_parts.append(f"{s['symbol']} ({s['signal']}, ${s['current_price']:.2f})")
        if len(valid_symbols) > 3:
            summary_parts.append(f"and {len(valid_symbols) - 3} more")

        return Response({
            "comparison_summary": " ".join(summary_parts),
            "symbols": symbols_data,
            "comparative_analysis": comparative_analysis,
            "count": len(valid_symbols)
        })


class BacktestStrategy(APIView):
    """
    Backtest a trading strategy on historical data.

    Answers "what-if" questions like:
    - "What if I bought AAPL 30 days ago?"
    - "What would my return be if I followed BUY signals for 90 days?"

    Query params:
    - symbol: Symbol ticker (required)
    - exchange: Exchange code (required)
    - days_ago: How many days back to start (default 30)
    - strategy: 'buy_hold' or 'signal_follow' (default 'buy_hold')
    - investment: Amount to invest (default 10000)
    """

    def get(self, request):
        symbol_ticker = request.query_params.get("symbol")
        exchange_code = request.query_params.get("exchange")
        days_ago = int(request.query_params.get("days_ago", 30))
        strategy = request.query_params.get("strategy", "buy_hold")
        investment = float(request.query_params.get("investment", 10000))

        if not symbol_ticker or not exchange_code:
            return Response(
                {"error": "Both symbol and exchange parameters are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get symbol
        try:
            exchange = Exchange.objects.get(code=exchange_code)
            symbol = Symbol.objects.get(symbol=symbol_ticker, exchange=exchange)
        except (Exchange.DoesNotExist, Symbol.DoesNotExist):
            return Response(
                {"error": f"Symbol {symbol_ticker}:{exchange_code} not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get historical data
        start_date = datetime.now().date() - timedelta(days=days_ago)
        historical = DaySymbol.objects.filter(
            symbol=symbol,
            date__gte=start_date
        ).order_by("date")

        if not historical.exists():
            return Response(
                {"error": "No historical data found for the specified period"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Execute strategy
        if strategy == "buy_hold":
            result = self._backtest_buy_hold(symbol, historical, investment)
        elif strategy == "signal_follow":
            result = self._backtest_signal_follow(symbol, historical, investment)
        else:
            return Response(
                {"error": f"Unknown strategy: {strategy}. Use 'buy_hold' or 'signal_follow'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(result)

    def _backtest_buy_hold(self, symbol, historical, investment):
        """
        Simple buy and hold strategy - buy at start, sell at end.
        """
        first_day = historical.first()
        last_day = historical.last()

        # Calculate shares purchased
        shares = investment / first_day.close

        # Calculate final value
        final_value = shares * last_day.close
        profit_loss = final_value - investment
        return_pct = (profit_loss / investment) * 100

        # Get any signal changes during period
        signal_changes = SignalHistory.objects.filter(
            symbol=symbol,
            date__gte=first_day.date,
            date__lte=last_day.date
        ).count()

        return {
            "strategy": "Buy and Hold",
            "symbol": f"{symbol.symbol}:{symbol.exchange.code}",
            "period": {
                "start_date": first_day.date.isoformat(),
                "end_date": last_day.date.isoformat(),
                "days": historical.count()
            },
            "investment": round(investment, 2),
            "execution": {
                "purchase_price": round(first_day.close, 2),
                "purchase_date": first_day.date.isoformat(),
                "shares_purchased": round(shares, 4),
                "sell_price": round(last_day.close, 2),
                "sell_date": last_day.date.isoformat()
            },
            "results": {
                "final_value": round(final_value, 2),
                "profit_loss": round(profit_loss, 2),
                "return_percent": round(return_pct, 2),
                "signal_changes_during_period": signal_changes
            },
            "summary": (
                f"Investing ${investment:,.2f} in {symbol.symbol} on {first_day.date} "
                f"would be worth ${final_value:,.2f} today "
                f"({'+' if profit_loss > 0 else ''}{return_pct:.2f}% return)"
            )
        }

    def _backtest_signal_follow(self, symbol, historical, investment):
        """
        Follow trading signals - buy on BUY/STRONG_BUY, sell on SELL/STRONG_SELL.
        """
        from decimal import Decimal

        cash = Decimal(str(investment))
        shares = Decimal("0")
        transactions = []
        position_open = False

        for day in historical:
            signal = day.status
            price = Decimal(str(day.close))

            # Buy signals
            if signal in ["BUY", "STRONG_BUY"] and not position_open and cash > 0:
                shares_to_buy = cash / price
                cost = shares_to_buy * price

                transactions.append({
                    "date": day.date.isoformat(),
                    "action": "BUY",
                    "signal": signal,
                    "price": float(price),
                    "shares": float(shares_to_buy),
                    "cost": float(cost)
                })

                shares += shares_to_buy
                cash -= cost
                position_open = True

            # Sell signals
            elif signal in ["SELL", "STRONG_SELL"] and position_open and shares > 0:
                proceeds = shares * price

                transactions.append({
                    "date": day.date.isoformat(),
                    "action": "SELL",
                    "signal": signal,
                    "price": float(price),
                    "shares": float(shares),
                    "proceeds": float(proceeds)
                })

                cash += proceeds
                shares = Decimal("0")
                position_open = False

        # Calculate final value (liquidate any remaining position)
        last_day = historical.last()
        if shares > 0:
            final_price = Decimal(str(last_day.close))
            cash += shares * final_price

        final_value = float(cash)
        profit_loss = final_value - investment
        return_pct = (profit_loss / investment) * 100

        return {
            "strategy": "Signal Following",
            "symbol": f"{symbol.symbol}:{symbol.exchange.code}",
            "period": {
                "start_date": historical.first().date.isoformat(),
                "end_date": historical.last().date.isoformat(),
                "days": historical.count()
            },
            "investment": round(investment, 2),
            "transactions": transactions,
            "results": {
                "final_value": round(final_value, 2),
                "profit_loss": round(profit_loss, 2),
                "return_percent": round(return_pct, 2),
                "total_trades": len(transactions),
                "final_position": "cash" if shares == 0 else f"{float(shares):.4f} shares"
            },
            "summary": (
                f"Following trading signals for {symbol.symbol} over {historical.count()} days "
                f"with ${investment:,.2f} investment resulted in ${final_value:,.2f} "
                f"({'+' if profit_loss > 0 else ''}{return_pct:.2f}% return) "
                f"with {len(transactions)} trades"
            )
        }


class MarketBenchmarks(APIView):
    """
    Get market index data for benchmarking.

    Query params:
    - indices: Comma-separated index symbols (e.g., "^GSPC,^IXIC")
    - days: Number of days of history (default 30)
    """

    def get(self, request):
        indices_param = request.query_params.get("indices", "^GSPC")  # Default to S&P 500
        days = int(request.query_params.get("days", 30))

        index_symbols = [s.strip() for s in indices_param.split(",")]

        results = []
        start_date = datetime.now().date() - timedelta(days=days)

        for index_symbol in index_symbols:
            try:
                index = MarketIndex.objects.get(symbol=index_symbol)

                # Get historical data
                historical = MarketIndexData.objects.filter(
                    index=index,
                    date__gte=start_date
                ).order_by("date")

                if not historical.exists():
                    continue

                first_day = historical.first()
                last_day = historical.last()

                # Calculate performance
                price_change = last_day.close - first_day.close
                pct_change = (price_change / first_day.close) * 100 if first_day.close != 0 else 0

                results.append({
                    "index": index.name,
                    "symbol": index.symbol,
                    "country": index.country,
                    "current_value": round(last_day.close, 2),
                    "period": {
                        "start_date": first_day.date.isoformat(),
                        "end_date": last_day.date.isoformat(),
                        "start_value": round(first_day.close, 2),
                        "end_value": round(last_day.close, 2)
                    },
                    "performance": {
                        "change": round(price_change, 2),
                        "change_percent": round(pct_change, 2)
                    },
                    "summary": (
                        f"{index.name} {'+' if price_change > 0 else ''}{pct_change:.2f}% "
                        f"over {historical.count()} days"
                    )
                })

            except MarketIndex.DoesNotExist:
                continue

        if not results:
            return Response(
                {"error": "No market index data found for the specified indices"},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({
            "benchmarks": results,
            "count": len(results)
        })


class DayTradingRecommendations(APIView):
    """
    Generate sophisticated day trading recommendations for intraday trading.

    Analyzes multiple factors to recommend 1-5 symbols most likely to increase
    during the trading day. Designed for same-day entry and exit.

    Query params:
    - bankroll: Starting capital (default 10000)
    - max_picks: Maximum number of recommendations (default 5)
    - min_score: Minimum confidence score threshold (default 60)
    - exchange: Filter by exchange code (optional)
    - refresh: Set to "true" to force recalculation (deletes existing recommendations for today)
    """

    @staticmethod
    def _safe_float(value, default=None):
        if value is None:
            return default
        try:
            f = float(value)
        except (TypeError, ValueError):
            return default
        if math.isfinite(f):
            return f
        return default

    def get(self, request):
        from decimal import Decimal

        bankroll = Decimal(str(request.query_params.get("bankroll", "10000")))
        max_picks = int(request.query_params.get("max_picks", 5))
        exchange_filter = request.query_params.get("exchange")
        force_refresh = request.query_params.get("refresh", "").lower() == "true"

        today = datetime.now().date()

        existing = DayTradingRecommendation.objects.filter(recommendation_date=today)
        if exchange_filter:
            existing = existing.filter(symbol__exchange__code=exchange_filter)

        if force_refresh and existing.exists():
            existing.delete()
            existing = DayTradingRecommendation.objects.none()

        if existing.exists():
            return self._format_existing_recommendations(existing, bankroll)

        # Fresh generation using trained model
        try:
            recommendations = generate_recommendations(
                trade_date=today,
                max_positions=max_picks,
                bankroll=float(bankroll),
                exchange_filter=exchange_filter,
            )
        except FileNotFoundError:
            return Response(
                {
                    "error": "Model file not found. Train the model via 'train_daytrading_model' command before requesting recommendations.",
                    "recommendations": [],
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not recommendations:
            return Response({
                "date": today.isoformat(),
                "bankroll": float(bankroll),
                "recommendations": [],
                "message": "No qualifying symbols met the strategy criteria today.",
                "analysis": {
                    "symbols_analyzed": Symbol.objects.count(),
                    "candidates_found": 0,
                }
            })

        def _safe_float(value, default=0.0):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        saved_recs = []
        for idx, rec in enumerate(recommendations, start=1):
            obv_status = _safe_float(rec.features.get("obv_status_num"), 0.0)
            signal_score = max(0, min(20, ((obv_status + 2) / 4) * 20))

            momentum = rec.features.get("momentum_5d")
            if momentum is None:
                momentum = rec.features.get("return_5d")
            momentum = _safe_float(momentum, 0.0)
            momentum_score = max(0, min(20, momentum * 400))

            volume_ratio = _safe_float(rec.features.get("volume_ratio_5d"), 1.0)
            volume_score = max(0, min(20, (volume_ratio - 0.5) * 20))

            technical_base = _safe_float(rec.features.get("rsi"), 50.0)
            technical_score = max(0, min(20, (technical_base - 30)))

            reason = f"Predicted return {rec.predicted_return:.2%}, ATR {rec.atr:.2f}, volume ratio {volume_ratio:.2f}"

            saved, _ = DayTradingRecommendation.objects.update_or_create(
                symbol=rec.symbol,
                recommendation_date=today,
                defaults={
                    "rank": idx,
                    "confidence_score": rec.confidence_score,
                    "recommended_allocation": rec.allocation,
                    "entry_price": rec.entry_price,
                    "target_price": rec.target_price,
                    "stop_loss_price": rec.stop_price,
                    "signal_score": signal_score,
                    "momentum_score": momentum_score,
                    "volume_score": volume_score,
                    "prediction_score": rec.predicted_return * 100,
                    "technical_score": technical_score,
                    "recommendation_reason": reason,
                }
            )
            saved_recs.append(saved)

        return Response(self._format_recommendations(saved_recs, bankroll))

    def _format_recommendations(self, recommendations, bankroll):
        """Format recommendations for API response"""
        rec_list = []
        total_allocated = Decimal("0")

        for rec in recommendations:
            shares = int(rec.recommended_allocation / Decimal(str(rec.entry_price))) if rec.entry_price else 0
            actual_cost = shares * Decimal(str(rec.entry_price)) if rec.entry_price else Decimal("0")
            total_allocated += actual_cost

            potential_gain = shares * (Decimal(str(rec.target_price)) - Decimal(str(rec.entry_price)))
            potential_loss = shares * (Decimal(str(rec.entry_price)) - Decimal(str(rec.stop_loss_price)))

            rec_list.append({
                "rank": rec.rank,
                "symbol": rec.symbol.symbol,
                "exchange": rec.symbol.exchange.code,
                "company_name": rec.symbol.name,
                "confidence_score": self._safe_float(round(rec.confidence_score, 1)),
                "entry_price": self._safe_float(round(rec.entry_price, 2)),
                "target_price": self._safe_float(round(rec.target_price, 2)),
                "stop_loss": self._safe_float(round(rec.stop_loss_price, 2)),
                "recommended_shares": shares,
                "position_cost": self._safe_float(actual_cost),
                "potential_gain": self._safe_float(potential_gain),
                "potential_loss": self._safe_float(potential_loss),
                "risk_reward_ratio": self._safe_float(potential_gain / potential_loss) if potential_loss > 0 else 0,
                "reason": rec.recommendation_reason,
                "score_breakdown": {
                    "signal": self._safe_float(round(rec.signal_score, 1)),
                    "momentum": self._safe_float(round(rec.momentum_score, 1)),
                    "volume": self._safe_float(round(rec.volume_score, 1)),
                    "prediction": self._safe_float(round(rec.prediction_score, 1)),
                    "technical": self._safe_float(round(rec.technical_score, 1))
                }
            })

        return {
            "date": recommendations[0].recommendation_date.isoformat(),
            "bankroll": self._safe_float(bankroll),
            "total_allocated": self._safe_float(total_allocated),
            "cash_reserve": self._safe_float(bankroll - total_allocated),
            "recommendations": rec_list,
            "strategy": "Day Trading - Buy at open, Sell before close",
            "risk_management": {
                "stop_loss_rule": "1.5% below entry",
                "target_profit": "2% above entry",
                "max_position_size": "35% of bankroll"
            },
            "analysis": {
                "picks_count": len(rec_list),
                "avg_confidence": self._safe_float(round(sum(r["confidence_score"] or 0 for r in rec_list) / len(rec_list), 1)) if rec_list else 0,
                "total_potential_gain": self._safe_float(sum(Decimal(str(r["potential_gain"])) for r in rec_list if r["potential_gain"] is not None)),
                "total_potential_loss": self._safe_float(sum(Decimal(str(r["potential_loss"])) for r in rec_list if r["potential_loss"] is not None))
            }
        }


    def _format_existing_recommendations(self, existing, bankroll):
        """Format already-generated recommendations"""
        return Response(self._format_recommendations(list(existing), bankroll))


class PortfolioTransactionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing portfolio transactions.

    Automatically updates:
    - Portfolio cash balance
    - Portfolio holdings
    - Average cost basis

    POST /api/transactions/ - Create a new transaction (BUY/SELL)
    GET /api/transactions/ - List all transactions
    GET /api/transactions/?portfolio=1 - Filter by portfolio
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see their own transactions
        queryset = PortfolioTransaction.objects.filter(portfolio__user=self.request.user)

        # Filter by portfolio if specified
        portfolio_id = self.request.query_params.get("portfolio")
        if portfolio_id:
            queryset = queryset.filter(portfolio_id=portfolio_id)

        return queryset

    def get_serializer_class(self):
        from .serializers_transactions import PortfolioTransactionCreateSerializer, PortfolioTransactionSerializer

        if self.action == "create":
            return PortfolioTransactionCreateSerializer
        return PortfolioTransactionSerializer

    def perform_create(self, serializer):
        """Validate portfolio ownership before creating transaction"""
        portfolio = serializer.validated_data.get("portfolio")
        if portfolio.user != self.request.user:
            msg = "You can only add transactions to your own portfolios"
            raise rest_serializers.ValidationError(msg)
        serializer.save()


class LivePrice(APIView):
    """
    Fetch Live/Current Price for a Symbol

    Fetches the most recent market price for a given symbol using Yahoo Finance.
    Updates the symbol's latest_price field in the database.

    **Query Parameters:**
    - `symbol`: Stock symbol (required, e.g., AAPL)
    - `exchange`: Exchange code (required, e.g., NASDAQ, TSE)

    **Returns:**
    ```json
    {
        "symbol": "AAPL",
        "exchange": "NASDAQ",
        "live_price": 178.25,
        "cached_price": 177.50,
        "price_updated_at": "2025-10-09T14:30:00Z",
        "data_source": "yahoo_finance",
        "market_status": "open"
    }
    ```

    **Examples:**
    - `/api/live-price/?symbol=AAPL&exchange=NASDAQ`
    - `/api/live-price/?symbol=SHOP&exchange=TSE`
    """

    def get(self, request):
        from decimal import Decimal, InvalidOperation

        from django.db import transaction as db_transaction
        from django.utils import timezone

        import yfinance as yf

        symbol_ticker = request.query_params.get("symbol")
        exchange_code = request.query_params.get("exchange")

        if not symbol_ticker or not exchange_code:
            return Response(
                {"error": "Both 'symbol' and 'exchange' parameters are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get symbol from database
        try:
            symbol = Symbol.objects.get(symbol=symbol_ticker, exchange__code=exchange_code)
        except Symbol.DoesNotExist:
            return Response(
                {"error": f"Symbol {symbol_ticker} not found on exchange {exchange_code}"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Store cached price before fetching
        cached_price = float(symbol.latest_price) if symbol.latest_price else float(symbol.last_close)
        cached_time = symbol.price_updated_at

        # Resolve ticker for Yahoo Finance (special handling for TSX)
        yf_ticker = f"{symbol_ticker}.TO" if exchange_code in ["TSE", "TO"] else symbol_ticker

        try:
            # Fetch live price from Yahoo Finance
            ticker = yf.Ticker(yf_ticker)

            live_price = None
            data_source = "yahoo_finance"

            # Try multiple methods to get the price
            try:
                # Method 1: regularMarketPrice from info
                live_price = ticker.info.get("regularMarketPrice")
                if not live_price:
                    # Method 2: currentPrice from info
                    live_price = ticker.info.get("currentPrice")
            except Exception:
                pass

            if not live_price:
                # Method 3: Latest close from history
                try:
                    hist = ticker.history(period="1d")
                    if not hist.empty:
                        live_price = hist["Close"].iloc[-1]
                except Exception:
                    pass

            if not live_price:
                return Response(
                    {
                        "error": f"Could not fetch live price for {symbol_ticker}",
                        "symbol": symbol_ticker,
                        "exchange": exchange_code,
                        "cached_price": cached_price,
                        "cached_time": cached_time
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            # Convert to Decimal safely
            try:
                live_price_decimal = Decimal(str(live_price)).quantize(Decimal("0.01"))
            except (InvalidOperation, TypeError):
                return Response(
                    {"error": "Invalid price data received"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Update symbol in database
            with db_transaction.atomic():
                symbol.latest_price = live_price_decimal
                symbol.price_updated_at = timezone.now()
                symbol.save(update_fields=["latest_price", "price_updated_at"])

            # Check market status
            from .tasks.portfolio_price_update import is_market_open
            market_open = is_market_open(exchange_code)

            # Calculate price change
            price_change = float(live_price_decimal) - cached_price
            price_change_percent = (price_change / cached_price * 100) if cached_price > 0 else 0

            return Response({
                "symbol": symbol_ticker,
                "exchange": exchange_code,
                "company_name": symbol.name,
                "live_price": float(live_price_decimal),
                "cached_price": cached_price,
                "price_change": round(price_change, 2),
                "price_change_percent": round(price_change_percent, 2),
                "price_updated_at": symbol.price_updated_at.isoformat(),
                "cached_time": cached_time.isoformat() if cached_time else None,
                "data_source": data_source,
                "market_status": "open" if market_open else "closed",
                "yahoo_finance_ticker": yf_ticker
            })

        except Exception as e:
            return Response(
                {
                    "error": f"Failed to fetch live price: {e!s}",
                    "symbol": symbol_ticker,
                    "exchange": exchange_code,
                    "cached_price": cached_price
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NewsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    News Articles with Sentiment Analysis

    Get news articles related to symbols with optional sentiment analysis.

    **Read-only endpoint** - only GET requests are allowed.

    **Query Parameters:**
    - `symbol`: Filter by stock symbol (requires `exchange`)
    - `exchange`: Filter by exchange code
    - `has_sentiment`: Filter by presence of sentiment analysis (true/false)
    - `sentiment_min`: Minimum sentiment score (1-10)
    - `sentiment_max`: Maximum sentiment score (1-10)
    - `days`: Number of days of history (default: 7)
    - `page_size`: Number of results per page (default: 30, max: 100)

    **Returns:**
    Each news article includes:
    - Article details (title, snippet, source, published date)
    - Sentiment analysis (if available)
    - List of related symbols

    **Examples:**
    - News for a symbol: `/api/news/?symbol=AAPL&exchange=NASDAQ`
    - Recent news (7 days): `/api/news/?days=7`
    - Positive sentiment only: `/api/news/?sentiment_min=7`
    - News with sentiment: `/api/news/?has_sentiment=true`
    """
    pagination_class = DaySymbolPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ["published_date", "created_at"]
    ordering = ["-published_date", "-created_at"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return NewsSerializer
        return NewsListSerializer

    def get_queryset(self):
        queryset = News.objects.all().prefetch_related("sentiment", "symbols")

        # Filter by symbol
        symbol_ticker = self.request.query_params.get("symbol")
        exchange_code = self.request.query_params.get("exchange")

        if symbol_ticker and exchange_code:
            # Get news for a specific symbol
            try:
                symbol = Symbol.objects.get(symbol=symbol_ticker, exchange__code=exchange_code)
                queryset = queryset.filter(symbols=symbol)
            except Symbol.DoesNotExist:
                return News.objects.none()

        # Filter by date range
        days = int(self.request.query_params.get("days", 7))
        if days > 0:
            from datetime import timedelta
            from django.utils import timezone
            cutoff_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(published_date__gte=cutoff_date)

        # Filter by sentiment presence
        has_sentiment = self.request.query_params.get("has_sentiment")
        if has_sentiment == "true":
            queryset = queryset.filter(sentiment__isnull=False)
        elif has_sentiment == "false":
            queryset = queryset.filter(sentiment__isnull=True)

        # Filter by sentiment score range
        sentiment_min = self.request.query_params.get("sentiment_min")
        if sentiment_min:
            try:
                queryset = queryset.filter(sentiment__sentiment_score__gte=int(sentiment_min))
            except (ValueError, TypeError):
                pass

        sentiment_max = self.request.query_params.get("sentiment_max")
        if sentiment_max:
            try:
                queryset = queryset.filter(sentiment__sentiment_score__lte=int(sentiment_max))
            except (ValueError, TypeError):
                pass

        return queryset


class NewsBySymbol(APIView):
    """
    Get News for a Specific Symbol

    Convenience endpoint to get recent news for a symbol with sentiment.

    **Query Parameters:**
    - `symbol`: Stock symbol (required)
    - `exchange`: Exchange code (required)
    - `limit`: Number of articles to return (default: 10, max: 50)

    **Returns:**
    ```json
    {
        "symbol": "AAPL",
        "exchange": "NASDAQ",
        "news_count": 5,
        "news": [
            {
                "id": 123,
                "title": "Apple Announces New Product",
                "snippet": "Apple Inc. today announced...",
                "source": "Reuters",
                "published_date": "2025-10-10T14:30:00Z",
                "sentiment": {
                    "sentiment_score": 8,
                    "justification": "Positive product announcement...",
                    "description": "The news indicates..."
                },
                "url": "https://..."
            }
        ]
    }
    ```

    **Example:** `/api/news/by-symbol/?symbol=AAPL&exchange=NASDAQ&limit=10`
    """

    def get(self, request):
        symbol_ticker = request.query_params.get("symbol")
        exchange_code = request.query_params.get("exchange")
        limit = int(request.query_params.get("limit", 10))
        limit = min(limit, 50)  # Max 50 articles

        if not symbol_ticker or not exchange_code:
            return Response(
                {"error": "Both 'symbol' and 'exchange' parameters are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            symbol = Symbol.objects.get(symbol=symbol_ticker, exchange__code=exchange_code)
        except Symbol.DoesNotExist:
            return Response(
                {"error": f"Symbol {symbol_ticker}:{exchange_code} not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get news for this symbol
        news_items = News.objects.filter(
            symbols=symbol
        ).prefetch_related("sentiment").order_by("-published_date", "-created_at")[:limit]

        serializer = NewsSerializer(news_items, many=True)

        return Response({
            "symbol": symbol.symbol,
            "exchange": symbol.exchange.code,
            "company_name": symbol.name,
            "news_count": len(news_items),
            "news": serializer.data
        })


class AnalyzeNewsSentiment(APIView):
    """
    Trigger Sentiment Analysis for News

    Manually trigger sentiment analysis for news articles.

    **POST Body:**
    ```json
    {
        "news_id": 123  // Optional - analyze specific article, or omit to analyze all pending
    }
    ```

    **Returns:**
    ```json
    {
        "message": "Sentiment analysis task queued",
        "task_id": "abc-123-def-456"
    }
    ```

    **Example:** `POST /api/news/analyze-sentiment/` with `{"news_id": 123}`
    """

    def post(self, request):
        news_id = request.data.get("news_id")

        # Trigger the Celery task
        from zimuabull.tasks.news_sentiment import analyze_news_sentiment

        if news_id:
            # Verify news exists
            try:
                news = News.objects.get(id=news_id)
            except News.DoesNotExist:
                return Response(
                    {"error": f"News article {news_id} not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            task = analyze_news_sentiment.delay(news_id=news_id)
            return Response({
                "message": f"Sentiment analysis queued for news article {news_id}",
                "task_id": str(task.id),
                "news_title": news.title
            })
        else:
            # Analyze all pending news
            pending_count = News.objects.filter(sentiment__isnull=True).count()

            if pending_count == 0:
                return Response({
                    "message": "No news articles need sentiment analysis"
                })

            task = analyze_news_sentiment.delay()
            return Response({
                "message": f"Sentiment analysis queued for {pending_count} news articles",
                "task_id": str(task.id),
                "pending_count": pending_count
            })


class MarketIndexViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List all market indices being tracked.

    **Read-only endpoint** - only GET requests are allowed.

    **Returns:** List of market indices (S&P 500, NASDAQ, etc.)

    **Example:**
    - Get all indices: `/api/market-indices/`
    """
    queryset = MarketIndex.objects.all()
    serializer_class = MarketIndexSerializer
    pagination_class = None  # No pagination for index list


class MarketIndexDataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Historical market index data for charting.

    **Read-only endpoint** - only GET requests are allowed.

    **Optional Query Parameters:**
    - `symbol`: Filter by index symbol (e.g., ^GSPC for S&P 500)
    - `start_date`: Start date for data range (YYYY-MM-DD)
    - `end_date`: End date for data range (YYYY-MM-DD)
    - `days`: Number of days of history (alternative to date range, e.g., 30, 90, 365)

    **Returns:** List of daily OHLCV data for market indices

    **Examples:**
    - Last 30 days of S&P 500: `/api/market-index-data/?symbol=^GSPC&days=30`
    - Date range for NASDAQ: `/api/market-index-data/?symbol=^IXIC&start_date=2024-01-01&end_date=2024-12-31`
    - All indices, last 90 days: `/api/market-index-data/?days=90`
    """
    serializer_class = MarketIndexDataListSerializer
    pagination_class = None  # No pagination for chart data

    def get_queryset(self):
        from datetime import datetime, timedelta

        queryset = MarketIndexData.objects.all().select_related('index')

        # Filter by symbol
        symbol = self.request.query_params.get('symbol')
        if symbol:
            queryset = queryset.filter(index__symbol=symbol)

        # Date filtering
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        days = self.request.query_params.get('days')

        if days:
            try:
                days_int = int(days)
                start_date_calc = datetime.now().date() - timedelta(days=days_int)
                queryset = queryset.filter(date__gte=start_date_calc)
            except ValueError:
                pass  # Ignore invalid days parameter

        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                queryset = queryset.filter(date__gte=start_date_obj)
            except ValueError:
                pass  # Ignore invalid start_date

        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(date__lte=end_date_obj)
            except ValueError:
                pass  # Ignore invalid end_date

        return queryset.order_by('index__symbol', 'date')


class WeeklyPerformance(APIView):
    """
    Get weekly performance analysis with technical indicators.

    Returns week-over-week price changes along with current technical indicators
    (RSI, OBV status, 30-day trend) and RSI changes.

    **Optional Query Parameters:**
    - `symbol`: Filter by specific ticker symbol
    - `exchange`: Filter by exchange code (NASDAQ, TSE, NYSE)
    - `min_change`: Minimum weekly % change (e.g., 5 for +5%, -10 for -10%)
    - `max_change`: Maximum weekly % change
    - `prediction`: Filter by latest prediction (POSITIVE, NEGATIVE, NEUTRAL)
    - `obv_status`: Filter by OBV status (BUY, SELL, HOLD, etc.)
    - `ordering`: Sort by (weekly_change, rsi_change, symbol) - default: weekly_change
    - `direction`: Sort direction (asc or desc) - default: desc
    - `page_size`: Results per page (default: 30)

    **Returns:** List of symbols with weekly performance and technical indicators

    **Examples:**
    - Top gainers this week: `/api/weekly-performance/?ordering=weekly_change&direction=desc`
    - Tech stocks with positive predictions: `/api/weekly-performance/?exchange=NASDAQ&prediction=POSITIVE`
    - Stocks up >5% with RSI improvement: `/api/weekly-performance/?min_change=5`
    """
    def get(self, request):
        from datetime import datetime, timedelta
        from django.db.models import F, OuterRef, Subquery

        # Get query parameters
        symbol_filter = request.query_params.get('symbol')
        exchange_filter = request.query_params.get('exchange')
        min_change = request.query_params.get('min_change')
        max_change = request.query_params.get('max_change')
        prediction_filter = request.query_params.get('prediction', '').upper()
        obv_filter = request.query_params.get('obv_status', '').upper()
        ordering = request.query_params.get('ordering', 'weekly_change')
        direction = request.query_params.get('direction', 'desc')
        page_size = int(request.query_params.get('page_size', 30))

        # Calculate dates
        today = datetime.now().date()
        one_week_ago = today - timedelta(days=7)

        # Get symbols with their latest data
        latest_data_subquery = DaySymbol.objects.filter(
            symbol=OuterRef('pk')
        ).order_by('-date')

        # Get data from 1 week ago
        week_ago_data_subquery = DaySymbol.objects.filter(
            symbol=OuterRef('pk'),
            date__lte=one_week_ago
        ).order_by('-date')

        # Get latest prediction
        latest_prediction_subquery = DayPrediction.objects.filter(
            symbol=OuterRef('pk')
        ).order_by('-date')

        # Build queryset with annotations
        symbols = Symbol.objects.annotate(
            latest_close=Subquery(latest_data_subquery.values('close')[:1]),
            latest_date=Subquery(latest_data_subquery.values('date')[:1]),
            latest_rsi_value=Subquery(latest_data_subquery.values('rsi')[:1]),
            week_ago_close=Subquery(week_ago_data_subquery.values('close')[:1]),
            week_ago_date=Subquery(week_ago_data_subquery.values('date')[:1]),
            week_ago_rsi=Subquery(week_ago_data_subquery.values('rsi')[:1]),
            latest_prediction=Subquery(latest_prediction_subquery.values('prediction')[:1])
        ).filter(
            latest_close__isnull=False,
            week_ago_close__isnull=False
        ).select_related('exchange')

        # Apply filters
        if symbol_filter:
            symbols = symbols.filter(symbol__icontains=symbol_filter)

        if exchange_filter:
            symbols = symbols.filter(exchange__code=exchange_filter)

        if obv_filter:
            symbols = symbols.filter(obv_status=obv_filter)

        if prediction_filter and prediction_filter in ['POSITIVE', 'NEGATIVE', 'NEUTRAL']:
            symbols = symbols.filter(latest_prediction=prediction_filter)

        # Calculate weekly changes in Python (can't do division in DB annotations easily)
        results = []
        for symbol in symbols:
            if symbol.week_ago_close and symbol.week_ago_close > 0:
                weekly_change = ((symbol.latest_close - symbol.week_ago_close) / symbol.week_ago_close) * 100

                # Calculate RSI change
                rsi_change = None
                if symbol.latest_rsi_value is not None and symbol.week_ago_rsi is not None:
                    rsi_change = symbol.latest_rsi_value - symbol.week_ago_rsi

                # Apply min/max change filters
                if min_change is not None:
                    try:
                        if weekly_change < float(min_change):
                            continue
                    except ValueError:
                        pass

                if max_change is not None:
                    try:
                        if weekly_change > float(max_change):
                            continue
                    except ValueError:
                        pass

                results.append({
                    'symbol': symbol.symbol,
                    'name': symbol.name,
                    'exchange': symbol.exchange.code,
                    'sector': symbol.sector,
                    'industry': symbol.industry,
                    'latest_close': round(symbol.latest_close, 2),
                    'latest_date': symbol.latest_date,
                    'week_ago_close': round(symbol.week_ago_close, 2),
                    'week_ago_date': symbol.week_ago_date,
                    'weekly_change': round(weekly_change, 2),
                    'latest_rsi': round(symbol.latest_rsi_value, 2) if symbol.latest_rsi_value else None,
                    'week_ago_rsi': round(symbol.week_ago_rsi, 2) if symbol.week_ago_rsi else None,
                    'rsi_change': round(rsi_change, 2) if rsi_change is not None else None,
                    'thirty_close_trend': round(symbol.thirty_close_trend, 2),
                    'obv_status': symbol.obv_status,
                    'latest_prediction': symbol.latest_prediction,
                    'accuracy': round(symbol.accuracy, 2) if symbol.accuracy else None
                })

        # Sort results
        reverse = (direction == 'desc')
        if ordering == 'weekly_change':
            results.sort(key=lambda x: x['weekly_change'], reverse=reverse)
        elif ordering == 'rsi_change':
            results.sort(key=lambda x: x['rsi_change'] if x['rsi_change'] is not None else -999, reverse=reverse)
        elif ordering == 'symbol':
            results.sort(key=lambda x: x['symbol'], reverse=reverse)
        else:
            results.sort(key=lambda x: x['weekly_change'], reverse=True)

        # Paginate
        page = int(request.query_params.get('page', 1))
        start = (page - 1) * page_size
        end = start + page_size
        paginated_results = results[start:end]

        return Response({
            'count': len(results),
            'page': page,
            'page_size': page_size,
            'results': paginated_results
        })
