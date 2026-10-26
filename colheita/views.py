from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from .models import Colheita
from .serializers import ColheitaSerializer
from funcionarios.models import Funcionario
from lotePlantio.models import LotePlantio, STATUS_EM_CULTIVO
from estoque.models import Estoque  # <-- Nova importação para automação!


class ColheitaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Colheita.objects.all()
    serializer_class = ColheitaSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        dados = request.data.copy()

        funcionario = Funcionario.do_usuario(request.user)
        dados['funcionario_id'] = funcionario.id

        serializer = self.get_serializer(data=dados)
        serializer.is_valid(raise_exception=True)

        lote = LotePlantio.objects.select_for_update().get(pk=serializer.validated_data['lote_id'].pk)
        qtd_colhida = serializer.validated_data['quantidade_colhida']
        qtd_perda = serializer.validated_data.get('quantidade_perda', 0)

        if lote.status not in STATUS_EM_CULTIVO:
            return Response(
                {"error": f"O lote #{lote.id} não está em cultivo ({lote.get_status_display()})."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if qtd_colhida <= 0 or qtd_perda < 0:
            return Response({"error": "Informe uma quantidade colhida maior que zero."},
                            status=status.HTTP_400_BAD_REQUEST)
        if qtd_colhida + qtd_perda > lote.quantidade:
            return Response(
                {"error": f"Colhido + perda ({qtd_colhida + qtd_perda:g}) passa do saldo do lote "
                          f"({lote.quantidade:g} {lote.unidade or 'unidades'})."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # A colheita encerra o lote: o que não foi colhido nem descartado também sai, como perda explícita
        restante = lote.quantidade - qtd_colhida - qtd_perda
        # A perda da colheita inclui a sobra, para o aproveitamento bater com o estoque
        serializer.save(quantidade_perda=qtd_perda + restante)
        baixas = [
            ('Saída', qtd_colhida, 'Baixa por Colheita'),
            ('Perda', qtd_perda, 'Descarte na Colheita'),
            ('Perda', restante, 'Saldo não colhido baixado no encerramento do lote'),
        ]
        for tipo, quantidade, motivo in baixas:
            if quantidade > 0:
                Estoque.objects.create(
                    lote_id=lote,
                    funcionario_id=funcionario,
                    tipo_movimentacao=tipo,
                    quantidade=quantidade,
                    unidade=lote.unidade or 'Unidades',
                    motivo=motivo,
                )

        lote.status = LotePlantio.StatusPlantio.COLHIDO
        lote.quantidade = 0
        lote.save()

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
