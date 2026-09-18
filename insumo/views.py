from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction

from .models import Insumo, MovimentacaoInsumo
from .serializers import InsumoSerializer, MovimentacaoInsumoSerializer


class InsumoViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Insumo.objects.all().order_by('nome')
    serializer_class = InsumoSerializer


class MovimentacaoInsumoViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = MovimentacaoInsumo.objects.all().order_by('-data_movimentacao')
    serializer_class = MovimentacaoInsumoSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        from funcionarios.models import Funcionario
        dados = request.data.copy()
        funcionario = Funcionario.objects.first()
        if funcionario:
            dados['funcionario_id'] = funcionario.id

        serializer = self.get_serializer(data=dados)
        serializer.is_valid(raise_exception=True)

        tipo = serializer.validated_data['tipo_movimentacao'].upper()
        qtd = serializer.validated_data['quantidade']
        insumo = serializer.validated_data['insumo_id']

        if tipo in ('ENTRADA', 'AJUSTE'):
            insumo.quantidade_atual += qtd
        elif tipo in ('SAIDA', 'SAÍDA', 'PERDA'):
            if insumo.quantidade_atual < qtd:
                return Response(
                    {"error": f"O insumo possui apenas {insumo.quantidade_atual} em estoque."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            insumo.quantidade_atual -= qtd
        insumo.save()

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)