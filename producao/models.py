from django.db import models
from estoque.models import Insumo, ProdutoFinal
from infraestrutura.models import Estufa


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


class Colheita(models.Model):
    lote = models.ForeignKey(LotePlantio, on_delete=models.CASCADE)
    produto_final = models.ForeignKey(ProdutoFinal, on_delete=models.CASCADE)
    data_colheita = models.DateField(auto_now_add=True)
    quantidade_colhida = models.FloatField()
    quantidade_perda = models.FloatField(default=0.0)

    class Meta:
        db_table = 'colheita'

    def __str__(self):
        return f"Colheita de {self.quantidade_colhida}kg do {self.lote}"