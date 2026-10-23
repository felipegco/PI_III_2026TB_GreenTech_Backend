from rest_framework import serializers
from .models import Alerta

UNIDADE = {
    Alerta.Parametro.TEMPERATURA: '°C',
    Alerta.Parametro.UMIDADE: '%',
    Alerta.Parametro.UMIDADE_SOLO: '%',
}


# Campos em camelCase porque seguem o formato que a AlertasView do front-end já usa
class AlertaSerializer(serializers.ModelSerializer):
    mesaId = serializers.IntegerField(source='mesa_id.id', read_only=True)
    mesaIdentificacao = serializers.CharField(source='mesa_id.identificacao', read_only=True)
    parametroNome = serializers.CharField(source='get_parametro_display', read_only=True)
    valor = serializers.FloatField(source='valor_lido', read_only=True)
    valorLido = serializers.SerializerMethodField()
    faixaEsperada = serializers.CharField(source='faixa_esperada', read_only=True)
    acaoSugerida = serializers.CharField(source='acao_sugerida', read_only=True)
    isPadrao = serializers.BooleanField(source='limite_padrao', read_only=True)
    simulado = serializers.SerializerMethodField()
    dataHora = serializers.DateTimeField(source='data_hora', read_only=True)
    atualizadoEm = serializers.DateTimeField(source='atualizado_em', read_only=True)
    resolvidoEm = serializers.DateTimeField(source='resolvido_em', read_only=True)
    resolvidoPor = serializers.CharField(source='resolvido_por.username', read_only=True, default=None)

    class Meta:
        model = Alerta
        fields = [
            'id', 'mesaId', 'mesaIdentificacao', 'parametro', 'parametroNome', 'gravidade', 'valor',
            'valorLido', 'faixaEsperada', 'mensagem', 'acaoSugerida', 'isPadrao', 'simulado', 'status',
            'dataHora', 'atualizadoEm', 'resolvidoEm', 'resolvidoPor',
        ]

    def get_valorLido(self, obj):
        return f'{float(obj.valor_lido):.1f} {UNIDADE[obj.parametro]}'

    def get_simulado(self, obj):
        # Alerta gerado a partir de leitura do simulador, e não de sensor físico
        return bool(obj.leitura and obj.leitura.simulado)
