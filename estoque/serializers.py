from rest_framework import serializers
from .models import Insumo, ProdutoFinal

class InsumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insumo
        fields = '__all__'

class ProdutoFinalSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProdutoFinal
        fields = '__all__'