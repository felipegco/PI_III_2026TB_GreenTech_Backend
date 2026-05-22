from rest_framework import serializers
from .models import RegistroClima, RegistroIrrigacao

class RegistroClimaSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroClima
        fields = '__all__'

class RegistroIrrigacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroIrrigacao
        fields = '__all__'