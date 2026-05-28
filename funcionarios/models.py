from django.db import models
from django.contrib.auth.models import User


class Funcionario(models.Model):
    nome_completo = models.CharField(max_length=150)
    cpf = models.CharField(max_length=14, unique=True)
    telefone = models.CharField(max_length=20, blank=True)

    # CARGOS_CHOICES = [
    #    ('gerente', 'Gerente'),
    #    ('operador', 'Operador'),
    #    ('tecnico', 'Técnico'),
    #]

    #cargo = models.CharField(max_length=50, choices=CARGOS_CHOICES)
    usuario = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='funcionario')

    class Meta:
        db_table = 'funcionarios'

    def __str__(self):
        return f"{self.nome_completo} ({self.get_cargo_display()})"