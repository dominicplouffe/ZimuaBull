from rest_framework import viewsets, filters
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from .models import Symbol, DaySymbol, DayPrediction, Favorite, Exchange, DayPredictionChoice, DaySymbolChoice
from .serializers import (
    SymbolSerializer,
    DaySymbolSerializer,
    DayPredictionSerializer,
    FavoriteSerializer,
    ExchangeSerializer,
)
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Max, F
from django.db import models
from datetime import date


class DaySymbolPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = 'page_size'
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


class SymbolViewSet(viewsets.ModelViewSet):
    """
    Stock Symbol Management

    Manage stock symbols tracked for a specific exchange (TSE, NASDAQ, NYSE).
    Each symbol includes technical indicators like OBV status, trend analysis, and prediction accuracy.

    **URL Structure:**
    - `/api/symbols/{exchange}/` - List all symbols for the given exchange code

    **Key Fields:**
    - `symbol`: Ticker symbol (e.g., "AAPL", "GOOGL")
    - `exchange`: Associated stock exchange with full details
    - `obv_status`: On-Balance Volume signal (BUY/SELL/HOLD/NA)
    - `thirty_close_trend`: 30-day trendline angle in degrees
    - `close_bucket`: Price trend classification (UP/DOWN/NA)
    - `accuracy`: Prediction accuracy percentage (0.0-1.0)

    **Example:** `/api/symbols/NASDAQ/`
    """
    serializer_class = SymbolSerializer

    def get_queryset(self):
        exchange_code = self.kwargs.get('exchange')
        if exchange_code:
            # Validate that the exchange exists
            exchange = get_object_or_404(Exchange, code=exchange_code)
            return Symbol.objects.filter(exchange=exchange).select_related('exchange')
        return Symbol.objects.none()


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
        symbol = request.query_params.get('symbol__symbol')
        exchange = request.query_params.get('symbol__exchange__code')

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
        symbol = request.query_params.get('symbol__symbol')
        exchange = request.query_params.get('symbol__exchange__code')

        if not symbol or not exchange:
            return Response(
                {"error": "Both 'symbol__symbol' and 'symbol__exchange__code' parameters are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get the limit parameter, default to 1 (latest record only)
        limit = request.query_params.get('limit', '1')
        try:
            limit = int(limit)
            if limit < 1:
                limit = 1
            if limit > 1000:
                limit = 1000
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
            favorites = [
                {"symbol": f.symbol.symbol, "exchange": f.symbol.exchange.code}
                for f in Favorite.objects.filter(user=user).select_related("symbol__exchange")
            ]

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
        date_str = request.query_params.get('date')

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
    - `page_size`: Number of results per page (default: 30, max: 1000)
    - `page`: Page number

    **Returns:** List of symbols with their latest prediction details

    **Examples:**
    - All positive predictions: `/api/symbols-by-prediction/?prediction=POSITIVE`
    - NASDAQ positive predictions: `/api/symbols-by-prediction/?prediction=POSITIVE&exchange=NASDAQ`
    - First 100 results: `/api/symbols-by-prediction/?prediction=NEGATIVE&page_size=100`
    """
    serializer_class = SymbolSerializer
    pagination_class = DaySymbolPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["symbol", "name"]
    ordering = ["symbol"]

    def get_queryset(self):
        prediction_type = self.request.query_params.get('prediction', '').upper()
        exchange_code = self.request.query_params.get('exchange')

        if not prediction_type:
            return Symbol.objects.none()

        if prediction_type not in [DayPredictionChoice.POSITIVE, DayPredictionChoice.NEGATIVE, DayPredictionChoice.NEUTRAL]:
            return Symbol.objects.none()

        # Get symbols that have predictions with the specified type
        # We want the latest prediction for each symbol
        symbol_ids = DayPrediction.objects.filter(
            prediction=prediction_type
        ).values('symbol_id').annotate(
            latest_date=Max('date')
        ).filter(
            date=F('latest_date')
        ).values_list('symbol_id', flat=True)

        queryset = Symbol.objects.filter(id__in=symbol_ids).select_related('exchange')

        if exchange_code:
            queryset = queryset.filter(exchange__code=exchange_code)

        return queryset

    def list(self, request, *args, **kwargs):
        prediction_type = request.query_params.get('prediction', '').upper()

        if not prediction_type:
            return Response(
                {"error": "Prediction parameter is required (POSITIVE, NEGATIVE, or NEUTRAL)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if prediction_type not in [DayPredictionChoice.POSITIVE, DayPredictionChoice.NEGATIVE, DayPredictionChoice.NEUTRAL]:
            return Response(
                {"error": f"Invalid prediction type. Must be POSITIVE, NEGATIVE, or NEUTRAL"},
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
        counts = Symbol.objects.values('obv_status').annotate(count=Count('id'))

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
            status_value = item['obv_status']
            count_value = item['count']
            if status_value in result:
                result[status_value] = count_value
            total += count_value

        result['total'] = total
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
        status_type = self.request.query_params.get('status', '').upper()
        exchange_code = self.request.query_params.get('exchange')

        if not status_type:
            return Symbol.objects.none()

        valid_statuses = [choice[0] for choice in DaySymbolChoice.choices]
        if status_type not in valid_statuses:
            return Symbol.objects.none()

        queryset = Symbol.objects.filter(obv_status=status_type).select_related('exchange')

        if exchange_code:
            queryset = queryset.filter(exchange__code=exchange_code)

        return queryset

    def list(self, request, *args, **kwargs):
        status_type = request.query_params.get('status', '').upper()

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
