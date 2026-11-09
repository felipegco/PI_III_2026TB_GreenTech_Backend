from rest_framework import serializers

from .models import LocalizacaoPropriedade


class LocalizacaoSerializer(serializers.ModelSerializer):
    atualizado_por_nome = serializers.SerializerMethodField()

    class Meta:
        model = LocalizacaoPropriedade
        fields = [
            'cidade', 'estado', 'pais', 'latitude', 'longitude', 'fuso_horario',
            'atualizado_em', 'atualizado_por_nome',
        ]
        read_only_fields = ['atualizado_em', 'atualizado_por_nome']

    def get_atualizado_por_nome(self, obj):
        usuario = obj.atualizado_por
        if not usuario:
            return None
        return usuario.get_full_name() or usuario.username

    def validate_latitude(self, valor):
        if not -90 <= valor <= 90:
            raise serializers.ValidationError('Latitude deve ficar entre -90 e 90.')
        return valor

    def validate_longitude(self, valor):
        if not -180 <= valor <= 180:
            raise serializers.ValidationError('Longitude deve ficar entre -180 e 180.')
        return valor
