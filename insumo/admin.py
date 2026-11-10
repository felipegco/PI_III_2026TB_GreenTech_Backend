from django.contrib import admin

from .models import PrevisaoEstoque


@admin.register(PrevisaoEstoque)
class PrevisaoEstoqueAdmin(admin.ModelAdmin):
    list_display = ('insumo', 'modelo', 'saldo_considerado', 'dias_restantes', 'data_esgotamento', 'gerada_em')
    list_filter = ('modelo',)
