from django.db import models
from django.contrib.auth.models import User


class Funcionario(models.Model):
    nome_completo = models.CharField(max_length=150)
    cpf = models.CharField(max_length=14, unique=True)
    telefone = models.CharField(max_length=20, blank=True)

    usuario = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='funcionario')

    class Meta:
        db_table = 'funcionarios'

    def __str__(self):
        return self.nome_completo