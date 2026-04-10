from django.db import models
from estufa.models import Estufa

class LotePlantio(models.Model):
    class StatusPlantio(models.TextChoices):
        ATIVO = 'AT', 'Ativo'
        COLHIDO = 'CO', 'Colhido'
        PERDIDO = 'PE', 'Perdido'

    estufa = models.ForeignKey(Estufa, on_delete=models.CASCADE)
    cultura = models.CharField(max_length=100)
    data_plantio = models.DateField()
    status = models.CharField(
        max_length=2,
        choices=StatusPlantio,
        default=StatusPlantio.ATIVO
    )
    custo_total = models.FloatField(default=0.0)

    class Meta:
        db_table = 'lote_plantio'

    def __str__(self):
        return f"Lote {self.id} - {self.cultura}"