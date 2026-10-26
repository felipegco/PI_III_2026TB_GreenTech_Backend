from rest_framework import serializers

from mesa.models import Mesa
from .models import LotePlantio, STATUS_EM_CULTIVO


def cultura_configurada(cultura):
    """Cultura criada pela nota fiscal vem com faixa e ciclo zerados até alguém completar o cadastro."""
    return cultura.tempo_medio_colheita > 0 and cultura.temperatura_minima < cultura.temperatura_maxima


class LotePlantioSerializer(serializers.ModelSerializer):
    status_nome = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = LotePlantio
        fields = '__all__'
        # Status só muda por ação (colheita ou registro de perda) e o saldo só por movimentação de estoque
        read_only_fields = ['status']

    def validate_quantidade(self, value):
        if self.instance is None and value <= 0:
            raise serializers.ValidationError('Informe quantas plantas/unidades foram plantadas.')
        if self.instance is not None and value != self.instance.quantidade:
            raise serializers.ValidationError('O saldo do lote muda só por movimentação de estoque ou colheita.')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is not None:
            for campo in ('mesa_id', 'cultura_id'):
                if campo in attrs and attrs[campo] != getattr(self.instance, campo):
                    raise serializers.ValidationError({campo: 'Mesa e cultura não mudam depois do plantio.'})
            return attrs

        mesa, cultura = attrs['mesa_id'], attrs['cultura_id']
        if mesa.estufa is None:
            raise serializers.ValidationError({'mesa_id': 'Escolha uma mesa que fique em uma estufa.'})
        if mesa.status_mesa == Mesa.Status.MANUTENCAO:
            raise serializers.ValidationError({'mesa_id': f'A mesa {mesa.identificacao} está em manutenção.'})
        ocupante = mesa.lotes_plantio.filter(status__in=STATUS_EM_CULTIVO).first()
        if ocupante:
            raise serializers.ValidationError({
                'mesa_id': f'A mesa {mesa.identificacao} já tem o lote #{ocupante.id} '
                           f'({ocupante.cultura_id}) em cultivo. Colha ou registre a perda antes de replantar.'
            })
        if mesa.capacidade_maxima and attrs.get('quantidade', 0) > mesa.capacidade_maxima:
            raise serializers.ValidationError({
                'quantidade': f'A mesa {mesa.identificacao} comporta até {mesa.capacidade_maxima:g} unidades.'
            })
        if not cultura_configurada(cultura):
            raise serializers.ValidationError({
                'cultura_id': f'Complete o cadastro de "{cultura}" (ciclo e faixa de temperatura) antes de plantar.'
            })
        return attrs


class RegistrarPerdaSerializer(serializers.Serializer):
    # Sem quantidade, a perda é do lote inteiro
    quantidade = serializers.FloatField(required=False, min_value=0.01)
    motivo = serializers.CharField(max_length=500)
