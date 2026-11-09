from django.contrib import admin

from .models import LocalizacaoPropriedade


@admin.register(LocalizacaoPropriedade)
class LocalizacaoPropriedadeAdmin(admin.ModelAdmin):
    list_display = ('cidade', 'estado', 'latitude', 'longitude', 'atualizado_em', 'atualizado_por')
