from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction

from estoque.models import Estoque
from funcionarios.models import Funcionario
from .models import LotePlantio, STATUS_EM_CULTIVO, STATUS_EM_ESTOQUE
from .serializers import LotePlantioSerializer, RegistrarPerdaSerializer

class LotePlantioViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = LotePlantio.objects.all().order_by('-id')
    serializer_class = LotePlantioSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        origem = serializer.validated_data.pop('lote_origem', None)
        usada = serializer.validated_data.pop('quantidade_origem', None)
        funcionario = Funcionario.do_usuario(request.user)

        if origem is not None and not serializer.validated_data.get('fornecedor'):
            serializer.validated_data['fornecedor'] = f'Transplante do lote #{origem.id} ({origem.mesa_id.identificacao})'
        # Todo plantio começa em cultivo, independente do que o cliente mandar
        lote = serializer.save(status=LotePlantio.StatusPlantio.ATIVO)

        if origem is not None:
            origem = LotePlantio.objects.select_for_update().get(pk=origem.pk)
            Estoque.objects.create(
                lote_id=origem,
                funcionario_id=funcionario,
                tipo_movimentacao='Saída',
                quantidade=usada,
                unidade=origem.unidade or 'Unidades',
                motivo=f'Transplante para a mesa {lote.mesa_id.identificacao} (lote #{lote.id})',
            )
            origem.quantidade -= usada
            if origem.quantidade <= 0:
                origem.quantidade = 0
                origem.status = LotePlantio.StatusPlantio.ESTOQUE_BAIXO
            origem.save()

        # criação automática do log no Estoque
        Estoque.objects.create(
            lote_id=lote,
            funcionario_id=funcionario,
            tipo_movimentacao='Entrada',
            quantidade=lote.quantidade,
            unidade=lote.unidade or 'Unidades',
            motivo='Entrada Inicial de Lote',
            observacoes=f'Fornecedor: {lote.fornecedor}' if lote.fornecedor else None,
        )

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def registrar_perda(self, request, pk=None):
        """Baixa plantas perdidas (praga, doença, clima). Perder o saldo todo encerra o lote como Perdido."""
        lote = LotePlantio.objects.select_for_update().get(pk=self.get_object().pk)
        if lote.status not in STATUS_EM_CULTIVO:
            return Response({'error': 'Só é possível registrar perda de um lote em cultivo.'},
                            status=status.HTTP_400_BAD_REQUEST)

        entrada = RegistrarPerdaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        quantidade = entrada.validated_data.get('quantidade', lote.quantidade)
        if quantidade > lote.quantidade:
            return Response({'error': f'O lote tem apenas {lote.quantidade:g} {lote.unidade or "unidades"}.'},
                            status=status.HTTP_400_BAD_REQUEST)

        Estoque.objects.create(
            lote_id=lote,
            funcionario_id=Funcionario.do_usuario(request.user),
            tipo_movimentacao='Perda',
            quantidade=quantidade,
            unidade=lote.unidade or 'Unidades',
            motivo=entrada.validated_data['motivo'],
        )
        lote.quantidade -= quantidade
        if lote.quantidade <= 0:
            lote.quantidade = 0
            lote.status = LotePlantio.StatusPlantio.PERDIDO
        lote.save()
        return Response(self.get_serializer(lote).data)

    def destroy(self, request, *args, **kwargs):
        is_superuser = request.user.is_superuser
        is_gerente = request.user.groups.filter(name__iexact='gerente').exists()
        is_admin = request.user.groups.filter(name__iexact='admin').exists()

        if not (is_superuser or is_gerente or is_admin):
            return Response(
            {"error": "Acesso negado. Exclusivo para gerentes e administradores."},
            status=status.HTTP_403_FORBIDDEN
        )

        # Lote com colheita ou já encerrado é histórico: some só por engano de cadastro, nunca depois
        lote = self.get_object()
        if lote.status not in STATUS_EM_CULTIVO + STATUS_EM_ESTOQUE or lote.colheita_set.exists():
            return Response(
                {"error": f"O lote #{lote.id} já tem histórico ({lote.get_status_display()}) e não pode ser excluído."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)
