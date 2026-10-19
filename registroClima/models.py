from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from mesa.models import Mesa

class RegistroClima(models.Model):
    mesa_id = models.ForeignKey(Mesa, on_delete=models.CASCADE, related_name='registros_clima')
    data_registro = models.DateTimeField(default=timezone.now)
    temperatura = models.DecimalField(max_digits=5, decimal_places=2)
    umidade = models.DecimalField(max_digits=10, decimal_places=2)
    # Em lux: estufas passam facilmente de 50.000 lux em dia de sol
    luminosidade = models.DecimalField(max_digits=8, decimal_places=2)
    ventilacao = models.IntegerField()

    # Sensores adicionais (opcionais para não invalidar leituras antigas)
    umidade_solo = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    co2 = models.DecimalField(
        max_digits=7, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(0)],
    )
    ph = models.DecimalField(
        max_digits=4, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(0), MaxValueValidator(14)],
    )
    observacoes = models.TextField(blank=True, null=True)

    def __str__(self):
        # Correção dos atributos para bater com a estrutura real do seu model
        return f"Mesa {self.mesa_id.id} - {self.data_registro.strftime('%d/%m/%Y %H:%M')}"

    class Meta:
        db_table = 'Registro_Clima'
        ordering = ['-data_registro']


class RegistroIrrigacao(models.Model):
    STATUS_CHOICES = [
        ('ativa', 'Ativa'),
        ('inativa', 'Inativa'),
    ]

    mesa_id = models.ForeignKey(Mesa, on_delete=models.CASCADE, related_name='registros_irrigacao')
    valvula_id = models.CharField(max_length=50)  # Ex: VLV-01
    data_registro = models.DateTimeField(default=timezone.now)
    status_atual = models.CharField(max_length=10, choices=STATUS_CHOICES, default='inativa')
    fluxo_l_min = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    consumo_ciclo_l = models.DecimalField(max_digits=6, decimal_places=2, default=0.0)
    observacoes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.valvula_id} ({self.status_atual}) - Mesa {self.mesa_id.id}"

    class Meta:
        db_table = 'Registro_Irrigacao'
        ordering = ['-data_registro']