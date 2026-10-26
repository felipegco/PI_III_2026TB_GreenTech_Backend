from rest_framework import serializers

from alerta.services import avaliar_leitura, faixa_da_mesa
from .models import RegistroClima, RegistroIrrigacao

class RegistroClimaSerializer(serializers.ModelSerializer):
    mesa_identificacao = serializers.ReadOnlyField(source='mesa_id.identificacao')
    avaliacao = serializers.SerializerMethodField()

    class Meta:
        model = RegistroClima
        fields = '__all__'

    def get_avaliacao(self, obj):
        """Mesma regra dos alertas, com a faixa atual da mesa (uma consulta por mesa na listagem)."""
        faixas = self.context.setdefault('_faixas_por_mesa', {})
        if obj.mesa_id_id not in faixas:
            faixas[obj.mesa_id_id] = faixa_da_mesa(obj.mesa_id)
        faixa, usou_padrao = faixas[obj.mesa_id_id]
        anomalias = avaliar_leitura(obj, faixa)
        gravidades = {a['gravidade'] for a in anomalias}
        return {
            'status': 'critico' if 'critico' in gravidades else 'atencao' if anomalias else 'normal',
            'parametros': [a['parametro'] for a in anomalias],
            'limite_padrao': usou_padrao,
        }

class RegistroIrrigacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroIrrigacao
        fields = '__all__'
