from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SymbolViewSet, DaySymbolViewSet, DayPredictionViewSet

router = DefaultRouter()
router.register(r"symbols", SymbolViewSet)
router.register(r"day-symbols", DaySymbolViewSet)
router.register(r"day-predictions", DayPredictionViewSet)

urlpatterns = [
    path("api/", include(router.urls)),
]
