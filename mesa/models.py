from django.db import models

from estufa.models import Estufa


class Mesa(models.Model):
    estufa_id = models.ForeignKey(Estufa, on_delete=models.CASCADE)
    indentificacao = models.CharField(max_length=100)
    capacidade = models.FloatField()
    status_mesa = models.CharField(max_length=100)
    observacoes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'mesa'

    def __str__(self):
        return f"{self.indentificacao}"

