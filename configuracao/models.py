from django.conf import settings
from django.db import models


class LocalizacaoPropriedade(models.Model):
    """
    Cidade onde ficam as estufas. Registro único (id 1): a previsão do tempo do painel e a previsão
    de chuva usada pela irrigação inteligente (RF10) saem dessas coordenadas.
    """
    cidade = models.CharField(max_length=120)
    estado = models.CharField(max_length=120, blank=True, default='')
    pais = models.CharField(max_length=80, blank=True, default='Brasil')
    latitude = models.DecimalField(max_digits=8, decimal_places=5)
    longitude = models.DecimalField(max_digits=8, decimal_places=5)
    fuso_horario = models.CharField(max_length=64, default='America/Sao_Paulo')
    atualizado_em = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        verbose_name = 'Localização da propriedade'
        verbose_name_plural = 'Localização da propriedade'

    def __str__(self):
        return f'{self.cidade} - {self.estado}' if self.estado else self.cidade

    @classmethod
    def atual(cls):
        """A localização configurada, ou None enquanto ninguém escolheu a cidade."""
        return cls.objects.filter(pk=1).first()
