from rest_framework import serializers
from .models import Estufa

class EstufaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estufa
        fields = '__all__'