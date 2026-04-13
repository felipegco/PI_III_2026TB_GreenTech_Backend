from rest_framework import serializers
from .models import Manejo


class ManejoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Manejo
        fields = '__all__'