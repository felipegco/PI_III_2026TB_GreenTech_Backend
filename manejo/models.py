from django.db import models
from lotePlantio.models import LotePlantio
from estoque.models import Insumo

class Manejo(models.Model):
    lote = models.ForeignKey(LotePlantio, on_delete=models.CASCADE)
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE)
    data_atividade = models.DateField(auto_now_add=True)
    tipo_atividade = models.CharField(max_length=100)
    quantidade_insumo_usada = models.FloatField()
    custo_atividade = models.FloatField()

    class Meta:
        db_table = 'manejo'

    def __str__(self):
        return f"{self.tipo_atividade} no {self.lote}"

