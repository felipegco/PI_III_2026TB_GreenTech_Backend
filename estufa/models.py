from django.db import models

class Estufa(models.Model):
    nome_setor = models.CharField(max_length=100)
    tipo_cultivo = models.CharField(max_length=50)
    capacidade_maxima = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.nome_setor