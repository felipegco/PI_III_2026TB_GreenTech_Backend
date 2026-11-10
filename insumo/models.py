from django.db import models
from funcionarios.models import Funcionario


class Insumo(models.Model):
    class TipoInsumo(models.TextChoices):
        FERTILIZANTE = 'FE', 'Fertilizante'
        DEFENSIVO = 'DF', 'Defensivo agrícola'
        SUBSTRATO = 'SB', 'Substrato'
        OUTRO = 'OU', 'Outro'

    nome = models.CharField(max_length=150)
    tipo = models.CharField(max_length=2, choices=TipoInsumo.choices, default=TipoInsumo.OUTRO)
    unidade = models.CharField(max_length=20)
    quantidade_atual = models.FloatField(default=0.0)
    estoque_minimo = models.FloatField(default=0.0)
    validade = models.DateField(blank=True, null=True)
    fornecedor = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        db_table = 'insumo'

    def __str__(self):
        return self.nome


class MovimentacaoInsumo(models.Model):
    insumo_id = models.ForeignKey(Insumo, on_delete=models.CASCADE, related_name='movimentacoes')
    funcionario_id = models.ForeignKey(Funcionario, on_delete=models.CASCADE)
    data_movimentacao = models.DateTimeField(auto_now_add=True)

    MOVIMENTACAO_CHOICES = [
        ('Entrada', 'Entrada'),
        ('Saída', 'Saída'),
        ('Perda', 'Perda'),
        ('Ajuste', 'Ajuste'),
    ]
    tipo_movimentacao = models.CharField(max_length=15, choices=MOVIMENTACAO_CHOICES)
    quantidade = models.FloatField()
    motivo = models.TextField(blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'movimentacao_insumo'

class PrevisaoEstoque(models.Model):
    """Última previsão de fim de estoque de um insumo (RF09). Recalculada quando o insumo se movimenta."""

    class Modelo(models.TextChoices):
        PROPHET = 'prophet', 'Prophet'
        MEDIA_MOVEL = 'media_movel', 'Média móvel'
        SEM_CONSUMO = 'sem_consumo', 'Sem consumo registrado'

    insumo = models.OneToOneField(Insumo, on_delete=models.CASCADE, related_name='previsao')
    modelo = models.CharField(max_length=15, choices=Modelo.choices)
    saldo_considerado = models.FloatField()
    consumo_medio_diario = models.FloatField(default=0.0)
    dias_restantes = models.IntegerField(blank=True, null=True)
    data_esgotamento = models.DateField(blank=True, null=True)
    dias_ate_minimo = models.IntegerField(blank=True, null=True)
    data_estoque_minimo = models.DateField(blank=True, null=True)
    percentual_restante = models.FloatField(default=0.0)
    dias_historico = models.IntegerField(default=0)
    observacao = models.CharField(max_length=255, blank=True, default='')
    ultima_movimentacao_id = models.IntegerField(blank=True, null=True)
    gerada_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'previsao_estoque'

    def __str__(self):
        return f'{self.insumo} esgota em {self.data_esgotamento or "?"} ({self.modelo})'
