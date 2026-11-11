from datetime import timedelta

from rest_framework import serializers
from .models import Cultura

class CulturaSerializer(serializers.ModelSerializer):
    total_colhido = serializers.FloatField(read_only=True)
    total_perda = serializers.FloatField(read_only=True)
    taxa_producao = serializers.FloatField(read_only=True)
    categoria_nome = serializers.CharField(source='get_categoria_display', read_only=True)
    lotes_ativos = serializers.IntegerField(read_only=True, default=0)
    # Lote em cultivo mais antigo: é o que fica pronto primeiro
    plantio_mais_antigo = serializers.DateField(read_only=True, default=None)
    mesa_proxima_colheita = serializers.CharField(read_only=True, default=None)
    proxima_colheita = serializers.SerializerMethodField()

    class Meta:
        model = Cultura
        fields = '__all__'

    def get_proxima_colheita(self, cultura):
        plantio = getattr(cultura, 'plantio_mais_antigo', None)
        if plantio is None or not cultura.tempo_medio_colheita:
            return None
        return (plantio + timedelta(days=cultura.tempo_medio_colheita)).isoformat()

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