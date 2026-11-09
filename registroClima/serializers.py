from rest_framework import serializers

from alerta.services import avaliar_leitura, faixa_da_mesa
from .models import DecisaoIrrigacao, ModoIrrigacao, RegistroClima, RegistroIrrigacao

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


class DecisaoIrrigacaoSerializer(serializers.ModelSerializer):
    """Formato combinado com a IrrigacaoView: horario, valvula, acao, confianca (0 a 1) e justificativa."""
    horario = serializers.DateTimeField(source='data_decisao', read_only=True)
    valvula = serializers.CharField(source='valvula_id', read_only=True)
    mesa = serializers.ReadOnlyField(source='mesa_id.identificacao')
    acao_nome = serializers.CharField(source='get_acao_display', read_only=True)
    confianca = serializers.FloatField(read_only=True)
    entradas = serializers.SerializerMethodField()

    class Meta:
        model = DecisaoIrrigacao
        fields = [
            'id', 'horario', 'valvula', 'mesa_id', 'mesa', 'acao', 'acao_nome', 'irrigar', 'confianca',
            'justificativa', 'entradas', 'modo', 'executada', 'registro_irrigacao', 'simulado',
        ]

    def get_entradas(self, obj):
        return {
            'umidade_solo': float(obj.umidade_solo),
            'temperatura': float(obj.temperatura),
            'umidade_ar': float(obj.umidade_ar),
            'chuva_prevista_mm': float(obj.chuva_prevista_mm),
            'previsao_disponivel': obj.previsao_disponivel,
            'valvula_estava_aberta': obj.valvula_estava_aberta,
        }


class ModoIrrigacaoSerializer(serializers.Serializer):
    modo = serializers.ChoiceField(choices=ModoIrrigacao.Modo.choices)
