from django.db import models

class Cultura(models.Model):
    nome_cultura = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    tempo_medio_colheita = models.IntegerField()
    temperatura_minima = models.DecimalField(max_digits=5, decimal_places=2)
    temperatura_maxima = models.DecimalField(max_digits=5, decimal_places=2)
    umidade_ideal = models.DecimalField(max_digits=5, decimal_places=2)
    observacoes = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nome_cultura

    class Meta:
        db_table = 'cultura'