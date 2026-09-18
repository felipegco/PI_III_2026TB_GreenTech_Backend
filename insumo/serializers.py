from rest_framework import serializers
from .models import Insumo, MovimentacaoInsumo


class InsumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insumo
        fields = '__all__'


class MovimentacaoInsumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovimentacaoInsumo
        fields = '__all__'