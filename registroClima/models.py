from django.db import models
from django.utils import timezone
from estufa.models import Estufa
from mesa.models import Mesa


class RegistroClima(models.Model):
    mesa_id = models.ForeignKey(Mesa, on_delete=models.CASCADE, related_name='registros_clima')
    data_registro = models.DateTimeField(default=timezone.now)
    temperatura = models.DecimalField(max_digits=5, decimal_places=2)
    umidade = models.DecimalField(max_digits=10, decimal_places=2)
    luminosidade = models.DecimalField(max_digits=5, decimal_places=2)
    ventilacao = models.IntegerField()
    observacoes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.estufa.nome_setor} - {self.data_leitura.strftime('%d/%m/%Y %H:%M')}"

    class Meta:
        db_table = 'Registro_Clima'