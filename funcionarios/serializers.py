from rest_framework import serializers
from .models import Funcionario


class FuncionarioSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='usuario.username', read_only=True)
    email = serializers.EmailField(source='usuario.email', read_only=True)
    cargo_display = serializers.CharField(source='get_cargo_display', read_only=True)
    data_entrada = serializers.DateTimeField(source='usuario.date_joined', read_only=True)

    class Meta:
        model = Funcionario
        fields = [
            'id',
            'nome_completo',
            'cpf',
            'telefone',
            'cargo',
            'cargo_display',
            'usuario',
            'username',
            'email',
            'data_entrada'
        ]
        read_only_fields = ['id', 'usuario', 'username', 'email', 'cargo_display', 'data_entrada']

class AlterarSenhaSerializer(serializers.Serializer):
    senha_atual = serializers.CharField(required=True)
    nova_senha = serializers.CharField(required=True)
    confirmar_senha = serializers.CharField(required=True)

    def validate(self, data):
        if data['nova_senha'] != data['confirmar_senha']:
            raise serializers.ValidationError({"confirmar_senha": "As senhas não coincidem."})
        return data