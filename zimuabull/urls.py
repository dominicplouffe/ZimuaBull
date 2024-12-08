from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SymbolViewSet,
    DaySymbolViewSet,
    DayPredictionViewSet,
    FavoriteList,
    AddFavorite,
    RemoveFavorite,
)

router = DefaultRouter()
router.register(r"symbols", SymbolViewSet)
router.register(r"day-symbols", DaySymbolViewSet)
router.register(r"day-predictions", DayPredictionViewSet)

urlpatterns = [
    path("api/", include(router.urls)),
    path("api/favorites", FavoriteList.as_view(), name="favorites"),
    path("api/favorites/add", AddFavorite.as_view(), name="add_favorite"),
    path("api/favorites/remove", RemoveFavorite.as_view(), name="remove_favorite"),
]
