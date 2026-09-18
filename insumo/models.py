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