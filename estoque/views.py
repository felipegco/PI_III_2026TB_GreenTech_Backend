from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction

from .models import Estoque
from .serializers import EstoqueSerializer


class EstoqueViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Estoque.objects.all().order_by('-data_movimentacao')
    serializer_class = EstoqueSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        dados = request.data.copy()

        from funcionarios.models import Funcionario
        funcionario = Funcionario.objects.first()
        if funcionario:
            dados['funcionario_id'] = funcionario.id

        serializer = self.get_serializer(data=dados)
        serializer.is_valid(raise_exception=True)

        tipo = serializer.validated_data['tipo_movimentacao'].upper()
        qtd = serializer.validated_data['quantidade']
        lote = serializer.validated_data['lote_id']

        if tipo == 'ENTRADA' or tipo == 'AJUSTE':
            lote.quantidade += qtd
        elif tipo in ['SAIDA', 'PERDA', 'SAÍDA']:
            if lote.quantidade < qtd:
                return Response(
                    {"error": f"Operação inválida. O lote possui apenas {lote.quantidade} itens."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            lote.quantidade -= qtd

        lote.save()

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)