from rest_framework import serializers
from .models import Mesa

class MesaSerializer(serializers.ModelSerializer):
    estufa_nome = serializers.ReadOnlyField(source='estufa.nome_setor')

    class Meta:
        model = Mesa
        fields = '__all__'