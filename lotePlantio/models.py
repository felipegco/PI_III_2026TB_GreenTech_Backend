from django.db import models

from cultura.models import Cultura
from estufa.models import Estufa
from mesa.models import Mesa


class LotePlantio(models.Model):

    cultura_id = models.ForeignKey(Cultura, on_delete=models.CASCADE, related_name='lotes_plantio')
    mesa_id = models.ForeignKey(Mesa, on_delete=models.CASCADE, related_name='lotes_plantio')
    data_plantio = models.DateField()

    class StatusPlantio(models.TextChoices):
        EM_ESTOQUE = 'ES', 'Em Estoque'
        ESTOQUE_BAIXO = 'BX', 'Estoque Baixo'
        DISPONIVEL = 'DI', 'Disponível'
        ATIVO = 'AT', 'Ativo'
        COLHIDO = 'CO', 'Colhido'
        PERDIDO = 'PE', 'Perdido'

    status = models.CharField(max_length=2, choices=StatusPlantio.choices, default=StatusPlantio.DISPONIVEL)

    quantidade = models.FloatField(default=0.0)
    unidade = models.CharField(max_length=20, blank=True, null=True)
    fornecedor = models.CharField(max_length=150, blank=True, null=True)
    validade = models.DateField(blank=True, null=True)


    class Meta:
        db_table = 'lote_plantio'

    def __str__(self):
        return f"Lote {self.id} - {self.cultura_id}"