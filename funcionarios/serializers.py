from rest_framework import serializers
from .models import Funcionario


class FuncionarioSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='usuario.username', read_only=True)
    email = serializers.EmailField(source='usuario.email', read_only=True)
    data_entrada = serializers.DateTimeField(source='usuario.date_joined', read_only=True)

    cargo_display = serializers.SerializerMethodField()
    is_gerente = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()

    class Meta:
        model = Funcionario
        fields = [
            'id', 'nome_completo', 'cpf', 'telefone',
            'usuario', 'username', 'email', 'data_entrada',
            'cargo_display', 'is_gerente', 'is_admin'
        ]
        read_only_fields = ['id', 'usuario', 'username', 'email', 'cargo_display', 'data_entrada']

    def get_cargo_display(self, obj):
        if obj.usuario:
            grupo = obj.usuario.groups.first()
            return grupo.name if grupo else "Sem Cargo Definido"
        return "Sem Cargo Definido"

    def get_is_gerente(self, obj):
        if obj.usuario:
            return obj.usuario.groups.filter(name__iexact='gerente').exists()
        return False

    def get_is_admin(self, obj):
        if obj.usuario:
            if obj.usuario.is_superuser: return True
            return obj.usuario.groups.filter(name__iexact='admin').exists()
        return False

class AlterarSenhaSerializer(serializers.Serializer):
    senha_atual = serializers.CharField(required=True)
    nova_senha = serializers.CharField(required=True)
    confirmar_senha = serializers.CharField(required=True)

    def validate(self, data):
        if data['nova_senha'] != data['confirmar_senha']:
            raise serializers.ValidationError({"confirmar_senha": "As senhas não coincidem."})
        return data