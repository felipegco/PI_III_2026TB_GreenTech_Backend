from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from .models import Colheita
from .serializers import ColheitaSerializer
from funcionarios.models import Funcionario
from lotePlantio.models import LotePlantio
from estoque.models import Estoque  # <-- Nova importação para automação!


class ColheitaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Colheita.objects.all()
    serializer_class = ColheitaSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        dados = request.data.copy()

        # 1. Identifica o funcionário logado
        try:
            funcionario = Funcionario.objects.get(usuario=request.user)
            dados['funcionario_id'] = funcionario.id
        except Funcionario.DoesNotExist:
            funcionario = Funcionario.objects.first()
            dados['funcionario_id'] = funcionario.id

        # 2. Salva o registro de Colheita Oficial
        serializer = self.get_serializer(data=dados)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        # Prepara as variáveis para a automação
        lote = LotePlantio.objects.get(id=dados['lote_id'])
        qtd_colhida = float(dados.get('quantidade_colhida', 0))
        qtd_perda = float(dados.get('quantidade_perda', 0))

        if qtd_colhida > 0:
            Estoque.objects.create(
                lote_id=lote,
                funcionario_id=funcionario,
                tipo_movimentacao='Saída',
                quantidade=qtd_colhida,
                unidade=lote.unidade or 'Unidades',
                motivo='Baixa por Colheita'
            )

        if qtd_perda > 0:
            Estoque.objects.create(
                lote_id=lote,
                funcionario_id=funcionario,
                tipo_movimentacao='Perda',
                quantidade=qtd_perda,
                unidade=lote.unidade or 'Unidades',
                motivo='Descarte na Colheita'
            )

        lote.status = 'CO'
        lote.quantidade = 0
        lote.save()

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)