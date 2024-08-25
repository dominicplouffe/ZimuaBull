from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Symbol, DaySymbol
from .serializers import SymbolSerializer, DaySymbolSerializer


class SymbolViewSet(viewsets.ModelViewSet):
    queryset = Symbol.objects.all()
    serializer_class = SymbolSerializer


class DaySymbolViewSet(viewsets.ModelViewSet):
    queryset = DaySymbol.objects.all()
    serializer_class = DaySymbolSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["symbol__symbol"]
    ordering_fields = ["date"]
    ordering = ["-date"]
