from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Funcionario

class FuncionarioSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Funcionario
        fields = ['id', 'nome_completo', 'cpf', 'telefone', 'cargo', 'username', 'password']

    def create(self, validated_data):
        # separam os dados, tirando o login e senha do pacote principal
        username = validated_data.pop('username', None)
        password = validated_data.pop('password', None)

        usuario_django = None

        if username and password:
            usuario_django = User.objects.create_user(
                username=username,
                password=password
            )

        # cria o Funcionario e aponta a chave estrangeira
        funcionario = Funcionario.objects.create(
            usuario=usuario_django,
            **validated_data
        )

        return funcionario