from django.db import models

from funcionarios.models import Funcionario
from lotePlantio.models import LotePlantio


class Estoque(models.Model):
    lote_id = models.ForeignKey(LotePlantio, on_delete=models.CASCADE)
    funcionario_id = models.ForeignKey(Funcionario, on_delete=models.CASCADE)
    data_movimentacao = models.DateField(auto_now_add=True)

    MOVIMENTACAO_CHOICES = [
        ('ENTRADA', 'Entrada'),
        ('SAIDA', 'Saída')
    ]
    tipo_movimentacao = models.CharField(max_length=10, choices=MOVIMENTACAO_CHOICES)
    quantidade = models.IntegerField()
    unidade = models.CharField(max_length=20)
    motivo = models.TextField(blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'estoque'

    def __str__(self):
        return self.lote_id.cultura