from rest_framework import serializers
from .models import Cultura

class CulturaSerializer(serializers.ModelSerializer):
    total_colhido = serializers.FloatField(read_only=True)
    total_perda = serializers.FloatField(read_only=True)
    taxa_producao = serializers.FloatField(read_only=True)

    class Meta:
        model = Cultura
        fields = '__all__'

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instancia = self.instance
        minima = attrs.get('temperatura_minima', getattr(instancia, 'temperatura_minima', None))
        maxima = attrs.get('temperatura_maxima', getattr(instancia, 'temperatura_maxima', None))
        ciclo = attrs.get('tempo_medio_colheita', getattr(instancia, 'tempo_medio_colheita', None))
        if minima is not None and maxima is not None and minima >= maxima:
            raise serializers.ValidationError({'temperatura_minima': 'A temperatura mínima deve ser menor que a máxima.'})
        if ciclo is not None and ciclo <= 0:
            raise serializers.ValidationError({'tempo_medio_colheita': 'Informe o ciclo até a colheita em dias.'})
        return attrs