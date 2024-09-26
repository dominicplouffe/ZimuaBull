from rest_framework import serializers
from .models import Symbol, DaySymbol, DayPrediction


class SymbolSerializer(serializers.ModelSerializer):

    class Meta:
        model = Symbol
        fields = "__all__"


class DaySymbolSerializer(serializers.ModelSerializer):
    symbol = SymbolSerializer()

    class Meta:
        model = DaySymbol
        fields = "__all__"


class DayPredictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DayPrediction
        fields = "__all__"
