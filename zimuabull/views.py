from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Symbol, DaySymbol, DayPrediction, Favorite
from .serializers import (
    SymbolSerializer,
    DaySymbolSerializer,
    DayPredictionSerializer,
    FavoriteSerializer,
)
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class SymbolViewSet(viewsets.ModelViewSet):
    queryset = Symbol.objects.all()
    serializer_class = SymbolSerializer


class DaySymbolViewSet(viewsets.ModelViewSet):
    queryset = DaySymbol.objects.all()
    serializer_class = DaySymbolSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["symbol__symbol"]
    ordering_fields = ["date"]
    ordering = ["date"]


class DayPredictionViewSet(viewsets.ModelViewSet):
    queryset = DayPrediction.objects.all()
    serializer_class = DayPredictionSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["symbol__symbol"]
    ordering_fields = ["date"]
    ordering = ["date"]


class FavoriteList(APIView):
    @method_decorator(login_required)
    def get(self, request):
        user = request.user
        if user.is_authenticated:
            favorites = [s.symbol.symbol for s in Favorite.objects.filter(user=user)]

            return Response(favorites, status=status.HTTP_200_OK)
        return Response([], status=status.HTTP_200_OK)


class AddFavorite(APIView):
    @method_decorator(login_required)
    def post(self, request):
        user = request.user
        symbol = request.data.get("symbol")
        symbol = Symbol.objects.get(symbol=symbol)
        favorite, _ = Favorite.objects.get_or_create(symbol=symbol, user=user)
        serializer = FavoriteSerializer(favorite)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RemoveFavorite(APIView):
    @method_decorator(login_required)
    def post(self, request):
        user = request.user
        symbol = request.data.get("symbol")
        symbol = Symbol.objects.get(symbol=symbol)
        for favorite in Favorite.objects.filter(symbol=symbol, user=user):
            favorite.delete()
        return Response([], status=status.HTTP_204_NO_CONTENT)
