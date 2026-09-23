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

    def destroy(self, request, *args, **kwargs):
        is_superuser = request.user.is_superuser
        is_gerente = request.user.groups.filter(name__iexact='gerente').exists()
        is_admin = request.user.groups.filter(name__iexact='admin').exists()

        if not (is_superuser or is_gerente or is_admin):
            return Response(
                {"error": "Acesso negado. Apenas gerentes e administradores podem excluir insumos."},
                status=status.HTTP_403_FORBIDDEN,
            )

        insumo = self.get_object()
        if insumo.quantidade_atual != 0:
            return Response(
                {"error": f"Só é possível excluir um insumo com saldo zerado. "
                          f"'{insumo.nome}' possui atualmente {insumo.quantidade_atual} "
                          f"{insumo.unidade} em estoque. Zere o saldo (ajustando ou excluindo "
                          f"as movimentações) antes de excluir o cadastro."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)


class MovimentacaoInsumoViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = MovimentacaoInsumo.objects.all().order_by('-data_movimentacao')
    serializer_class = MovimentacaoInsumoSerializer

    ENTRADA_TIPOS = ('ENTRADA', 'AJUSTE')
    SAIDA_TIPOS = ('SAIDA', 'SAÍDA', 'PERDA')

    @staticmethod
    def _is_admin_ou_gerente(user):
        if user.is_superuser:
            return True
        return user.groups.filter(name__iexact='gerente').exists() or \
            user.groups.filter(name__iexact='admin').exists()

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        from funcionarios.models import Funcionario
        dados = request.data.copy()

        tipo_solicitado = str(dados.get('tipo_movimentacao', '')).strip().upper()

        # Usuários sem cargo de gerente/admin só podem lançar saídas de estoque.
        if not self._is_admin_ou_gerente(request.user) and tipo_solicitado not in self.SAIDA_TIPOS:
            return Response(
                {"error": "Acesso negado. Apenas gerentes e administradores podem lançar "
                          "movimentações de entrada, ajuste ou perda. Usuários comuns só podem "
                          "registrar saídas de estoque."},
                status=status.HTTP_403_FORBIDDEN,
            )

        funcionario = Funcionario.objects.filter(usuario=request.user).first()
        if not funcionario:
            funcionario = Funcionario.objects.first()
        if funcionario:
            dados['funcionario_id'] = funcionario.id

        serializer = self.get_serializer(data=dados)
        serializer.is_valid(raise_exception=True)

        tipo = serializer.validated_data['tipo_movimentacao'].upper()
        qtd = serializer.validated_data['quantidade']
        insumo = serializer.validated_data['insumo_id']

        if tipo in self.ENTRADA_TIPOS:
            insumo.quantidade_atual += qtd
        elif tipo in self.SAIDA_TIPOS:
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

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        # Apenas gerentes e administradores podem apagar histórico de movimentação.
        if not self._is_admin_ou_gerente(request.user):
            return Response(
                {"error": "Acesso negado. Apenas gerentes e administradores podem excluir "
                          "movimentações do histórico."},
                status=status.HTTP_403_FORBIDDEN,
            )

        movimentacao = self.get_object()
        insumo = movimentacao.insumo_id
        tipo = (movimentacao.tipo_movimentacao or '').strip().upper()
        qtd = movimentacao.quantidade

        # Desfaz no estoque exatamente o efeito que esta movimentação causou,
        # para que apagar o histórico nunca deixe a quantidade do insumo
        # "órfã" (sem nenhuma movimentação que a justifique).
        if tipo in self.ENTRADA_TIPOS:
            nova_quantidade = insumo.quantidade_atual - qtd
            if nova_quantidade < 0:
                return Response(
                    {"error": f"Não é possível excluir: o insumo já teve {qtd} unidades "
                              f"consumidas em movimentações posteriores. Estoque atual: "
                              f"{insumo.quantidade_atual}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            insumo.quantidade_atual = nova_quantidade
        elif tipo in self.SAIDA_TIPOS:
            insumo.quantidade_atual += qtd

        insumo.save()

        return super().destroy(request, *args, **kwargs)