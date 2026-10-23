from django.conf import settings
from django.db import models
from django.utils import timezone

from mesa.models import Mesa
from registroClima.models import RegistroClima


class Alerta(models.Model):

    class Parametro(models.TextChoices):
        TEMPERATURA = 'temperatura', 'Temperatura'
        UMIDADE = 'umidade', 'Umidade'
        UMIDADE_SOLO = 'umidade_solo', 'Umidade do solo'

    class Gravidade(models.TextChoices):
        ATENCAO = 'atencao', 'Atenção'
        CRITICO = 'critico', 'Crítico'

    class Status(models.TextChoices):
        ATIVO = 'ativo', 'Ativo'
        RESOLVIDO = 'resolvido', 'Resolvido'

    mesa_id = models.ForeignKey(Mesa, on_delete=models.CASCADE, related_name='alertas')
    # Leitura mais recente que manteve o alerta aberto
    leitura = models.ForeignKey(RegistroClima, on_delete=models.SET_NULL, null=True, related_name='alertas')
    parametro = models.CharField(max_length=20, choices=Parametro.choices)
    gravidade = models.CharField(max_length=10, choices=Gravidade.choices)
    valor_lido = models.DecimalField(max_digits=8, decimal_places=2)
    faixa_esperada = models.CharField(max_length=50)
    mensagem = models.CharField(max_length=255)
    acao_sugerida = models.CharField(max_length=255)
    # True quando a mesa não tem cultura vinculada e foi usada a faixa padrão
    limite_padrao = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVO)
    data_hora = models.DateTimeField(default=timezone.now)
    atualizado_em = models.DateTimeField(default=timezone.now)
    resolvido_em = models.DateTimeField(blank=True, null=True)
    resolvido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name='alertas_resolvidos',
    )

    def __str__(self):
        return f"{self.get_parametro_display()} ({self.gravidade}) - Mesa {self.mesa_id.id}"

    class Meta:
        db_table = 'alerta'
        ordering = ['-atualizado_em']
