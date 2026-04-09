from rest_framework import serializers
from .models import LotePlantio


class LotePlantioSerializer(serializers.ModelSerializer):
    class Meta:
        model = LotePlantio
        fields = '__all__'