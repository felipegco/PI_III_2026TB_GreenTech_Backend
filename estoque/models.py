from django.db import models

from funcionarios.models import Funcionario
from lotePlantio.models import LotePlantio


class Estoque(models.Model):
    lote_id = models.ForeignKey(LotePlantio, on_delete=models.CASCADE)
    funcionario_id = models.ForeignKey(Funcionario, on_delete=models.CASCADE)
    data_movimentacao = models.DateTimeField(auto_now_add=True)

    MOVIMENTACAO_CHOICES = [
        ('Entrada', 'Entrada'),
        ('Saída', 'Saída'),
        ('Perda', 'Perda'),
        ('Ajuste', 'Ajuste')
    ]
    tipo_movimentacao = models.CharField(max_length=15, choices=MOVIMENTACAO_CHOICES)

    quantidade = models.FloatField()
    unidade = models.CharField(max_length=20)
    motivo = models.TextField(blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'estoque'

    def __str__(self):
        return f"Movimentação Lote {self.lote.id} - {self.tipo_movimentacao}"