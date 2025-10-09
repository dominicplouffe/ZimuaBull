from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExchangeViewSet,
    SymbolViewSet,
    DaySymbolViewSet,
    DayPredictionViewSet,
    FavoriteList,
    AddFavorite,
    RemoveFavorite,
    PredictionCountByDate,
    SymbolsByPrediction,
    DaySymbolChoiceCount,
    SymbolsByStatus,
    PortfolioViewSet,
    PortfolioHoldingViewSet,
    PortfolioSummary,
    RecalculateSignals,
    SignalExplanation,
    SymbolSearch,
    LLMContext,
    ChatWithLLM,
    SaveChatResponse,
    ConversationList,
    ConversationDetail,
    CompareSymbols,
    BacktestStrategy,
    MarketBenchmarks,
    DayTradingRecommendations,
    PortfolioTransactionViewSet,
    LivePrice,
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

urlpatterns = [
    path("api/", include(router.urls)),
    path("api/symbols/<str:exchange>/", SymbolViewSet.as_view({'get': 'list'}), name="symbols-list"),
    path("api/favorites", FavoriteList.as_view(), name="favorites"),
    path("api/favorites/add", AddFavorite.as_view(), name="add_favorite"),
    path("api/favorites/remove", RemoveFavorite.as_view(), name="remove_favorite"),
    path("api/prediction-count/", PredictionCountByDate.as_view(), name="prediction-count"),
    path("api/symbol-status-count/", DaySymbolChoiceCount.as_view(), name="symbol-status-count"),
    path("api/portfolio-summary/", PortfolioSummary.as_view(), name="portfolio-summary"),
    path("api/recalculate-signals/", RecalculateSignals.as_view(), name="recalculate-signals"),
    path("api/signal-explanation/", SignalExplanation.as_view(), name="signal-explanation"),
    # LLM Integration endpoints
    path("api/llm-context/", LLMContext.as_view(), name="llm-context"),
    path("api/chat/", ChatWithLLM.as_view(), name="chat"),
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
]
