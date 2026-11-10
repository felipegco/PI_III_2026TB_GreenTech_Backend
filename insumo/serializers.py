from rest_framework import serializers
from .models import Insumo, MovimentacaoInsumo, PrevisaoEstoque


class InsumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Insumo
        fields = '__all__'


class MovimentacaoInsumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovimentacaoInsumo
        fields = '__all__'

class PrevisaoEstoqueSerializer(serializers.ModelSerializer):
    """Formato do PrevisaoEstoqueWidget: id e dados do insumo, dias restantes, percentual e data estimada."""
    id = serializers.IntegerField(source='insumo.id', read_only=True)
    nome = serializers.CharField(source='insumo.nome', read_only=True)
    categoria = serializers.CharField(source='insumo.get_tipo_display', read_only=True)
    unidade = serializers.CharField(source='insumo.unidade', read_only=True)
    quantidadeAtual = serializers.FloatField(source='insumo.quantidade_atual', read_only=True)
    estoqueMinimo = serializers.FloatField(source='insumo.estoque_minimo', read_only=True)
    diasRestantes = serializers.IntegerField(source='dias_restantes', read_only=True)
    dataEstimada = serializers.DateField(source='data_esgotamento', read_only=True)
    diasAteMinimo = serializers.IntegerField(source='dias_ate_minimo', read_only=True)
    estoqueMinimoEm = serializers.DateField(source='data_estoque_minimo', read_only=True)
    percentualRestante = serializers.FloatField(source='percentual_restante', read_only=True)
    consumoMedioDiario = serializers.FloatField(source='consumo_medio_diario', read_only=True)
    modeloNome = serializers.CharField(source='get_modelo_display', read_only=True)
    diasHistorico = serializers.IntegerField(source='dias_historico', read_only=True)
    geradaEm = serializers.DateTimeField(source='gerada_em', read_only=True)

    class Meta:
        model = PrevisaoEstoque
        fields = [
            'id', 'nome', 'categoria', 'unidade', 'quantidadeAtual', 'estoqueMinimo', 'diasRestantes',
            'dataEstimada', 'diasAteMinimo', 'estoqueMinimoEm', 'percentualRestante', 'consumoMedioDiario',
            'modelo', 'modeloNome', 'diasHistorico', 'observacao', 'geradaEm',
        ]
