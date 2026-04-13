from rest_framework import serializers
from .models import Colheita

class ColheitaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Colheita
        fields = '__all__'