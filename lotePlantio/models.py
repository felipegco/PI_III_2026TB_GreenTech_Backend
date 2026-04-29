from django.db import models
from estufa.models import Estufa


class LotePlantio(models.Model):
    class StatusPlantio(models.TextChoices):
        EM_ESTOQUE = 'ES', 'Em Estoque'
        ESTOQUE_BAIXO = 'BX', 'Estoque Baixo'
        DISPONIVEL = 'DI', 'Disponível'
        ATIVO = 'AT', 'Ativo'
        COLHIDO = 'CO', 'Colhido'
        PERDIDO = 'PE', 'Perdido'

    estufa = models.ForeignKey(Estufa, on_delete=models.CASCADE)

    cultura = models.CharField(max_length=100)
    fornecedor = models.CharField(max_length=150, blank=True, null=True)

    data_plantio = models.DateField()
    validade = models.DateField(blank=True, null=True)

    status = models.CharField(
        max_length=2,
        choices=StatusPlantio.choices,
        default=StatusPlantio.ATIVO
    )

    custo = models.FloatField(default=0.0)
    custo_total = models.FloatField(default=0.0)

    quantidade = models.FloatField(default=0.0)
    unidade = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        db_table = 'lote_plantio'

    def __str__(self):
        return f"Lote {self.id} - {self.cultura}"