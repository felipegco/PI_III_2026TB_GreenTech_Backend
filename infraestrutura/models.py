from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class Estufa(models.Model):
    nome_setor = models.CharField(max_length=100)
    tipo_cultivo = models.CharField(max_length=50)
    capacidade_maxima = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.nome_setor


class RegistroClima(models.Model):
    estufa = models.ForeignKey(Estufa, on_delete=models.CASCADE)
    data_leitura = models.DateTimeField(default=timezone.now)
    temperatura = models.DecimalField(max_digits=5, decimal_places=2)
    umidade = models.DecimalField(max_digits=10, decimal_places=2)
    origem_dado = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.estufa.nome_setor} - {self.data_leitura.strftime('%d/%m/%Y %H:%M')}"


class Funcionario(models.Model):
    nome_completo = models.CharField(max_length=150)
    cpf = models.CharField(max_length=14, unique=True)
    telefone = models.CharField(max_length=20, blank=True)

    class Cargos(models.TextChoices):
        GERENTE = 'GE', 'Gerente da Estufa'
        AGRONOMO = 'AG', 'Agrônomo'
        OPERADOR = 'OP', 'Operador de Manejo'

    cargo = models.CharField(max_length=2, choices=Cargos, default=Cargos.OPERADOR)
    usuario = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='funcionario')

    def __str__(self):
        return f"{self.nome_completo} ({self.get_cargo_display()})"