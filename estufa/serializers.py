from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from .models import Estufa


class EstufaSerializer(serializers.ModelSerializer):
    capacidade_alocada = serializers.SerializerMethodField()
    capacidade_disponivel = serializers.SerializerMethodField()

    class Meta:
        model = Estufa
        fields = '__all__'

    def _alocada(self, obj):
        total = obj.mesas.aggregate(total=Sum('capacidade_maxima'))['total']
        return total or Decimal('0')

    def get_capacidade_alocada(self, obj):
        return self._alocada(obj)

    def get_capacidade_disponivel(self, obj):
        return obj.capacidade_maxima - self._alocada(obj)

    def validate_capacidade_maxima(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('A capacidade da estufa não pode ser negativa.')

        # Não deixa reduzir a estufa abaixo do que as mesas já ocupam.
        if self.instance is not None:
            alocada = self._alocada(self.instance)
            if value < alocada:
                raise serializers.ValidationError(
                    f'As mesas desta estufa já somam {alocada}. '
                    f'A capacidade não pode ser menor que isso (informado: {value}).'
                )
        return value
