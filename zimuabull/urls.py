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
)

router = DefaultRouter()
router.register(r"exchanges", ExchangeViewSet)
router.register(r"day-symbols", DaySymbolViewSet)
router.register(r"day-predictions", DayPredictionViewSet)
router.register(r"symbols-by-prediction", SymbolsByPrediction, basename="symbols-by-prediction")
router.register(r"symbols-by-status", SymbolsByStatus, basename="symbols-by-status")

urlpatterns = [
    path("api/", include(router.urls)),
    path("api/symbols/<str:exchange>/", SymbolViewSet.as_view({'get': 'list'}), name="symbols-list"),
    path("api/favorites", FavoriteList.as_view(), name="favorites"),
    path("api/favorites/add", AddFavorite.as_view(), name="add_favorite"),
    path("api/favorites/remove", RemoveFavorite.as_view(), name="remove_favorite"),
    path("api/prediction-count/", PredictionCountByDate.as_view(), name="prediction-count"),
    path("api/symbol-status-count/", DaySymbolChoiceCount.as_view(), name="symbol-status-count"),
]
