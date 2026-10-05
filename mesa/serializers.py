from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from estufa.models import Estufa
from .models import Mesa


class MesaSerializer(serializers.ModelSerializer):
    estufa_nome = serializers.ReadOnlyField(source='estufa.nome_setor')

    class Meta:
        model = Mesa
        fields = '__all__'

    def validate_capacidade_maxima(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('A capacidade da mesa não pode ser negativa.')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        instance = self.instance
        estufa = attrs.get('estufa', instance.estufa if instance else None)
        capacidade = attrs.get(
            'capacidade_maxima',
            instance.capacidade_maxima if instance else Decimal('0'),
        )

        # Mesa sem estufa vinculada não consome capacidade de nenhum setor.
        if estufa is None:
            return attrs

        # Em edição, só revalida se a estufa ou a capacidade mudaram. Assim uma
        # mesa antiga (já acima do limite) ainda pode ter observações/status editados.
        if instance and estufa == instance.estufa and capacidade == instance.capacidade_maxima:
            return attrs

        # Trava a linha da estufa para duas requisições simultâneas não estourarem o limite.
        estufa = Estufa.objects.select_for_update().get(pk=estufa.pk)

        outras_mesas = Mesa.objects.filter(estufa=estufa)
        if instance:
            outras_mesas = outras_mesas.exclude(pk=instance.pk)
        ja_alocado = outras_mesas.aggregate(total=Sum('capacidade_maxima'))['total'] or Decimal('0')
        disponivel = estufa.capacidade_maxima - ja_alocado

        if capacidade > disponivel:
            raise serializers.ValidationError({
                'capacidade_maxima': (
                    f'A estufa "{estufa.nome_setor}" tem capacidade {estufa.capacidade_maxima}, '
                    f'já alocada: {ja_alocado}, disponível: {max(disponivel, Decimal("0"))}. '
                    f'A mesa não pode ter capacidade {capacidade}.'
                )
            })

        return attrs
