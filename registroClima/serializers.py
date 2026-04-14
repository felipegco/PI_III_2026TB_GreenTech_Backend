from rest_framework import serializers
from .models import RegistroClima


class RegistroClimaSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroClima
        fields = '__all__'