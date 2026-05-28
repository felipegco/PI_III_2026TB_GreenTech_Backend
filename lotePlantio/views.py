from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction

from .models import LotePlantio
from .serializers import LotePlantioSerializer

class LotePlantioViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = LotePlantio.objects.all().order_by('-id')
    serializer_class = LotePlantioSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lote = serializer.save()

        # criação automática do log no Estoque
        from estoque.models import Estoque
        from funcionarios.models import Funcionario

        funcionario = Funcionario.objects.first()
        Estoque.objects.create(
            lote_id=lote,
            funcionario_id=funcionario,
            tipo_movimentacao='ENTRADA',
            quantidade=lote.quantidade,
            unidade=lote.unidade or 'Unidades',
            motivo='Entrada Inicial de Lote',
            observacoes=f'Fornecedor: {lote.fornecedor}'
        )

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        is_superuser = request.user.is_superuser
        is_gerente = request.user.groups.filter(name__iexact='gerente').exists()
        is_admin = request.user.groups.filter(name__iexact='admin').exists()

        if not (is_superuser or is_gerente or is_admin):
            return Response(
            {"error": "Acesso negado. Exclusivo para gerentes e administradores."},
            status=status.HTTP_403_FORBIDDEN
        )

        return super().destroy(request, *args, **kwargs)