from django.contrib import admin
from django import forms
from django.contrib.auth.models import Group, User
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import Funcionario

# =========================================================
# 1. CUSTOMIZAÇÃO DA TELA DE FUNCIONÁRIOS
# =========================================================

class FuncionarioAdminForm(forms.ModelForm):
    grupo_de_acesso = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=True,
        label="Cargo / Grupo de Acesso",
        help_text="Selecione o nível de permissão deste funcionário no sistema."
    )

    class Meta:
        model = Funcionario
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.usuario:
            grupo_atual = self.instance.usuario.groups.first()
            if grupo_atual:
                self.fields['grupo_de_acesso'].initial = grupo_atual

    def save(self, commit=True):
        funcionario = super().save(commit=False)
        if commit:
            funcionario.save()

        if funcionario.usuario:
            grupo_selecionado = self.cleaned_data.get('grupo_de_acesso')
            funcionario.usuario.groups.clear()
            if grupo_selecionado:
                funcionario.usuario.groups.add(grupo_selecionado)

        return funcionario


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    form = FuncionarioAdminForm
    list_display = ('nome_completo', 'cpf', 'get_grupo')
    search_fields = ('nome_completo', 'cpf')

    def get_grupo(self, obj):
        if obj.usuario:
            grupo = obj.usuario.groups.first()
            return grupo.name if grupo else "Sem Acesso"
        return "Sem Acesso"

    get_grupo.short_description = "Cargo (Grupo)"


# =========================================================
# 2. CUSTOMIZAÇÃO DA TELA DE USUÁRIOS (Segurança Extra)
# =========================================================

admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )