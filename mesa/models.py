from django.db import models
from estufa.models import Estufa

class Mesa(models.Model):

    class Status(models.TextChoices):
        LIVRE = 'livre', 'Livre'
        MANUTENCAO = 'manutencao', 'Em manutenção'
        # Nunca gravado: é devolvido pela API quando a mesa tem lote em cultivo
        OCUPADA = 'ocupada', 'Ocupada'

    estufa = models.ForeignKey(Estufa, on_delete=models.CASCADE, related_name='mesas', db_column='estufa_id', null=True)
    identificacao = models.CharField(max_length=50)
    capacidade_maxima = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    status_mesa = models.CharField(max_length=30, choices=Status.choices, default=Status.LIVRE)
    observacoes = models.TextField(blank=True, null=True)

    def lote_em_cultivo(self):
        return self.lotes_plantio.filter(status='AT').order_by('-data_plantio', '-id').first()

    def __str__(self):
        return f"{self.identificacao} - {self.estufa.nome_setor}"

    class Meta:
        db_table = 'mesa'
        unique_together = ('estufa', 'identificacao')