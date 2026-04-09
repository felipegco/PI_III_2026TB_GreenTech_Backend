from django.db import models
from django.utils import timezone
from estufa.models import Estufa

class RegistroClima(models.Model):
    estufa = models.ForeignKey(Estufa, on_delete=models.CASCADE)
    data_leitura = models.DateTimeField(default=timezone.now)
    temperatura = models.DecimalField(max_digits=5, decimal_places=2)
    umidade = models.DecimalField(max_digits=10, decimal_places=2)
    origem_dado = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.estufa.nome_setor} - {self.data_leitura.strftime('%d/%m/%Y %H:%M')}"

    class Meta:
        db_table = 'Registro_Clima'