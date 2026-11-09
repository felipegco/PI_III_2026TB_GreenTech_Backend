from django.conf import settings
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
    # True quando a leitura veio do simulador, e não de um sensor físico
    simulado = models.BooleanField(default=False)
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
    # True quando o registro veio do simulador, e não de uma válvula física
    simulado = models.BooleanField(default=False)
    observacoes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.valvula_id} ({self.status_atual}) - Mesa {self.mesa_id.id}"

    class Meta:
        db_table = 'Registro_Irrigacao'
        ordering = ['-data_registro']

class ModoIrrigacao(models.Model):
    """Registro único (id 1): no MANUAL a IA só sugere; no AUTOMATICO_IA a decisão aciona a válvula."""

    class Modo(models.TextChoices):
        MANUAL = 'MANUAL', 'Manual'
        AUTOMATICO_IA = 'AUTOMATICO_IA', 'Automático (IA)'

    modo = models.CharField(max_length=20, choices=Modo.choices, default=Modo.MANUAL)
    atualizado_em = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        db_table = 'Modo_Irrigacao'
        verbose_name = 'Modo de irrigação'
        verbose_name_plural = 'Modo de irrigação'

    def __str__(self):
        return self.get_modo_display()

    @classmethod
    def atual(cls):
        return cls.objects.get_or_create(pk=1)[0]


class DecisaoIrrigacao(models.Model):
    """Decisão da árvore (RF10) para uma válvula, com as entradas usadas e a explicação."""

    class Acao(models.TextChoices):
        ABRIR = 'abrir', 'Abrir válvula'
        FECHAR = 'fechar', 'Fechar válvula'
        MANTER_ABERTA = 'manter_aberta', 'Manter aberta'
        MANTER_FECHADA = 'manter_fechada', 'Manter fechada'

    mesa_id = models.ForeignKey(Mesa, on_delete=models.CASCADE, related_name='decisoes_irrigacao')
    valvula_id = models.CharField(max_length=50)
    data_decisao = models.DateTimeField(default=timezone.now)
    acao = models.CharField(max_length=20, choices=Acao.choices)
    irrigar = models.BooleanField()
    confianca = models.DecimalField(max_digits=5, decimal_places=4)
    justificativa = models.TextField()

    # Entradas da árvore no momento da decisão
    leitura = models.ForeignKey(RegistroClima, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    umidade_solo = models.DecimalField(max_digits=5, decimal_places=2)
    temperatura = models.DecimalField(max_digits=5, decimal_places=2)
    umidade_ar = models.DecimalField(max_digits=10, decimal_places=2)
    chuva_prevista_mm = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    previsao_disponivel = models.BooleanField(default=False)
    valvula_estava_aberta = models.BooleanField(default=False)

    modo = models.CharField(max_length=20, choices=ModoIrrigacao.Modo.choices)
    # True quando a decisão virou comando na válvula (RegistroIrrigacao); no manual é só sugestão
    executada = models.BooleanField(default=False)
    registro_irrigacao = models.ForeignKey(
        RegistroIrrigacao, null=True, blank=True, on_delete=models.SET_NULL, related_name='decisoes',
    )
    modelo_treinado_em = models.CharField(max_length=40, blank=True, default='')
    simulado = models.BooleanField(default=False)

    class Meta:
        db_table = 'Decisao_Irrigacao'
        ordering = ['-data_decisao', '-id']

    def __str__(self):
        return f'{self.valvula_id}: {self.get_acao_display()} ({self.confianca:.0%})'
