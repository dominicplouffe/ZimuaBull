from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .views import (
    AddFavorite,
    AnalyzeNewsSentiment,
    BacktestStrategy,
    ChatWithLLM,
    CompareSymbols,
    ConversationDetail,
    ConversationList,
    DayPredictionViewSet,
    DaySymbolChoiceCount,
    DaySymbolViewSet,
    DayTradingRecommendations,
    ExchangeViewSet,
    FavoriteList,
    LivePrice,
    LLMContext,
    MarketBenchmarks,
    MarketIndexDataViewSet,
    MarketIndexViewSet,
    NewsBySymbol,
    NewsViewSet,
    PortfolioHoldingViewSet,
    PortfolioSummary,
    PortfolioTransactionViewSet,
    PortfolioViewSet,
    PredictionCountByDate,
    RemoveFavorite,
    SaveChatResponse,
    SignalExplanation,
    SymbolsByPrediction,
    SymbolsByStatus,
    SymbolSearch,
    WeeklyPerformance,
    chat_stream,
)

router = DefaultRouter()
router.register(r"exchanges", ExchangeViewSet)
router.register(r"day-symbols", DaySymbolViewSet)
router.register(r"day-predictions", DayPredictionViewSet)
router.register(r"symbols-by-prediction", SymbolsByPrediction, basename="symbols-by-prediction")
router.register(r"symbols-by-status", SymbolsByStatus, basename="symbols-by-status")
router.register(r"symbol-search", SymbolSearch, basename="symbol-search")
router.register(r"portfolios", PortfolioViewSet, basename="portfolios")
router.register(r"holdings", PortfolioHoldingViewSet, basename="holdings")
router.register(r"transactions", PortfolioTransactionViewSet, basename="transactions")
router.register(r"news", NewsViewSet, basename="news")
router.register(r"market-indices", MarketIndexViewSet, basename="market-indices")
router.register(r"market-index-data", MarketIndexDataViewSet, basename="market-index-data")

urlpatterns = [
    # News - MUST come before router.urls to avoid conflicts
    path("api/news/by-symbol/", NewsBySymbol.as_view(), name="news-by-symbol"),
    path("api/news/analyze-sentiment/", AnalyzeNewsSentiment.as_view(), name="analyze-news-sentiment"),
    # Router URLs
    path("api/", include(router.urls)),
    path("api/favorites", FavoriteList.as_view(), name="favorites"),
    path("api/favorites/add", AddFavorite.as_view(), name="add_favorite"),
    path("api/favorites/remove", RemoveFavorite.as_view(), name="remove_favorite"),
    path("api/prediction-count/", PredictionCountByDate.as_view(), name="prediction-count"),
    path("api/symbol-status-count/", DaySymbolChoiceCount.as_view(), name="symbol-status-count"),
    path("api/portfolio-summary/", PortfolioSummary.as_view(), name="portfolio-summary"),
    path("api/signal-explanation/", SignalExplanation.as_view(), name="signal-explanation"),
    # LLM Integration endpoints
    path("api/llm-context/", LLMContext.as_view(), name="llm-context"),
    path("api/chat/", ChatWithLLM.as_view(), name="chat"),
    path("api/chat/stream/", chat_stream, name="chat-stream"),
    path("api/chat-response/", SaveChatResponse.as_view(), name="chat-response"),
    path("api/conversations/", ConversationList.as_view(), name="conversations"),
    path("api/conversations/<int:conversation_id>/", ConversationDetail.as_view(), name="conversation-detail"),
    path("api/compare-symbols/", CompareSymbols.as_view(), name="compare-symbols"),
    path("api/backtest/", BacktestStrategy.as_view(), name="backtest"),
    path("api/market-benchmarks/", MarketBenchmarks.as_view(), name="market-benchmarks"),
    # Day Trading
    path("api/day-trading-recommendations/", DayTradingRecommendations.as_view(), name="day-trading-recommendations"),
    # Live Price
    path("api/live-price/", LivePrice.as_view(), name="live-price"),
    # Weekly Performance
    path("api/weekly-performance/", WeeklyPerformance.as_view(), name="weekly-performance"),
]
