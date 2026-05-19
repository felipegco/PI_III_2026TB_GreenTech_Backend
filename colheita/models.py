from django.db import models

from funcionarios.models import Funcionario
from lotePlantio.models import LotePlantio

class Colheita(models.Model):
    lote_id = models.ForeignKey(LotePlantio, on_delete=models.CASCADE)
    funcionario_id = models.ForeignKey(Funcionario, on_delete=models.CASCADE)
    data_colheita = models.DateField(auto_now_add=True)
    quantidade_colhida = models.FloatField()
    quantidade_perda = models.FloatField(default=0.0)

    class Meta:
        db_table = 'colheita'

    def __str__(self):
        return f"Colheita de {self.quantidade_colhida}kg do {self.lote}"