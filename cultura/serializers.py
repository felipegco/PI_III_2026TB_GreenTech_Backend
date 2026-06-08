from rest_framework import serializers
from .models import Cultura

class CulturaSerializer(serializers.ModelSerializer):
    total_colhido = serializers.FloatField(read_only=True)
    total_perda = serializers.FloatField(read_only=True)
    taxa_producao = serializers.FloatField(read_only=True)

    class Meta:
        model = Cultura
        fields = '__all__'