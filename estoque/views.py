from datetime import date

from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction

from .models import Estoque
from .serializers import EstoqueSerializer
from .ocr_utils import extrair_texto_arquivo, extrair_dados_nota, NotaFiscalOcrError
from insumo.models import Insumo, MovimentacaoInsumo


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

    def destroy(self, request, *args, **kwargs):
        is_superuser = request.user.is_superuser
        is_gerente = request.user.groups.filter(name__iexact='gerente').exists()
        is_admin = request.user.groups.filter(name__iexact='admin').exists()

        if not (is_superuser or is_gerente or is_admin):
            return Response(
                {"error": "Acesso negado. Apenas gerentes e administradores podem eliminar registos do histórico."},
                status=status.HTTP_403_FORBIDDEN
            )

        return super().destroy(request, *args, **kwargs)


class OcrNotaFiscalView(APIView):
    """
    POST /api/estoque/ocr-nota-fiscal/

    Recebe um arquivo (campo "documento", multipart/form-data) e devolve
    os dados extraídos da nota fiscal no formato:

        {
            "numero": "000.142.891",
            "dataEmissao": "2026-09-01",
            "fornecedor": "AgroQuímica Soluções Rurais Ltda",
            "itens": [
                {"descricao": "Nitrato de Cálcio", "quantidade": 50, "unidade": "kg", "valor": 450.0}
            ]
        }

    A extração é feita por regras/regex simples (ver estoque/ocr_utils.py),
    sem motor de OCR de imagem. Ver limitações no topo daquele arquivo.

    Observação: esta view NÃO classifica os itens como insumo ou cultura —
    essa decisão é feita pelo usuário na tela de revisão manual (RF11) e
    enviada no campo "tipo" de cada item ao chamar /confirmar-lote-nf/.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        arquivo = request.FILES.get('documento')
        if not arquivo:
            return Response(
                {"error": "Nenhum arquivo enviado. Envie o campo 'documento'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            texto = extrair_texto_arquivo(arquivo)
            dados = extrair_dados_nota(texto)
        except NotaFiscalOcrError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response(dados, status=status.HTTP_200_OK)


class ConfirmarLoteNfView(APIView):
    """
    POST /api/estoque/confirmar-lote-nf/

    Recebe o mesmo formato devolvido por /estoque/ocr-nota-fiscal/, já
    revisado e classificado manualmente pelo usuário na tela (RF11). Cada
    item DEVE trazer um campo "tipo" com valor "insumo" ou "cultura":

        {
            "numero": "000.142.891",
            "fornecedor": "AgroQuímica Soluções Rurais Ltda",
            "dataEmissao": "2026-09-01",
            "itens": [
                {"descricao": "Nitrato de Cálcio", "quantidade": 50, "unidade": "kg", "tipo": "insumo"},
                {"descricao": "Alface Crespa", "quantidade": 200, "unidade": "un", "tipo": "cultura"}
            ]
        }

    Comportamento por tipo de item:

    - tipo == "insumo": busca (ou cria) um Insumo pelo nome e soma a
      quantidade recebida a ele, registrando uma MovimentacaoInsumo do tipo
      Entrada. NUNCA cria Cultura nem LotePlantio para esses itens — é
      exatamente essa mistura que fazia produtos químicos aparecerem como
      lotes "prontos para colheita" no frontend.

    - tipo == "cultura": mantém o comportamento original —
        - Tenta encontrar uma Cultura já cadastrada cujo nome combine com a
          descrição do item (comparação case-insensitive, por substring nos
          dois sentidos).
        - Se encontrar a Cultura, procura um LotePlantio existente dela (em
          estoque/disponível) e soma a quantidade recebida a esse lote.
        - Se não encontrar Cultura nem Lote correspondentes, CRIA
          automaticamente uma nova Cultura e um novo LotePlantio para o item.
        - Gera um registro de movimentação em Estoque (tipo Entrada).

    Tudo roda dentro de uma transação: se algo falhar, nada é gravado.
    """
    permission_classes = [IsAuthenticated]

    MESA_PLACEHOLDER_ID = 'NF-AUTO'
    TIPOS_VALIDOS = ('insumo', 'cultura')

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        from cultura.models import Cultura
        from lotePlantio.models import LotePlantio
        from mesa.models import Mesa
        from funcionarios.models import Funcionario

        dados = request.data
        itens = dados.get('itens')

        if not itens or not isinstance(itens, list):
            return Response(
                {"error": "Nenhum item informado para confirmar a entrada em estoque."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        numero_nf = dados.get('numero')
        fornecedor_nf = dados.get('fornecedor')
        data_emissao = self._parse_data(dados.get('dataEmissao'))

        funcionario = Funcionario.objects.filter(usuario=request.user).first()
        if not funcionario:
            funcionario = Funcionario.objects.first()
        if not funcionario:
            return Response(
                {"error": "Nenhum funcionário cadastrado para associar à movimentação."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resultados = []

        for indice, item in enumerate(itens):
            descricao = (item.get('descricao') or '').strip()
            quantidade = item.get('quantidade')
            unidade = (item.get('unidade') or '').strip() or 'un'
            tipo_item = (item.get('tipo') or '').strip().lower()

            if not descricao or quantidade in (None, ''):
                return Response(
                    {"error": f"Item {indice + 1} inválido: 'descricao' e 'quantidade' são obrigatórios."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if tipo_item not in self.TIPOS_VALIDOS:
                return Response(
                    {"error": f"Item {indice + 1} inválido: informe 'tipo' como 'insumo' ou 'cultura'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                quantidade = float(quantidade)
            except (TypeError, ValueError):
                return Response(
                    {"error": f"Item {indice + 1}: quantidade inválida."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if tipo_item == 'insumo':
                resultados.append(
                    self._processar_insumo(
                        descricao, quantidade, unidade, funcionario, numero_nf, fornecedor_nf
                    )
                )
                continue

            # tipo_item == 'cultura' — fluxo original, sem alterações de comportamento
            cultura = self._encontrar_cultura(Cultura, descricao)
            criou_cultura = False
            if cultura is None:
                cultura = self._criar_cultura_automatica(Cultura, descricao, numero_nf, fornecedor_nf)
                criou_cultura = True

            lote = self._encontrar_lote_disponivel(LotePlantio, cultura)
            criou_lote = False
            if lote is None:
                lote = self._criar_lote_automatico(
                    LotePlantio, Mesa, cultura, unidade, fornecedor_nf, data_emissao
                )
                criou_lote = True

            lote.quantidade = (lote.quantidade or 0) + quantidade
            if not lote.unidade:
                lote.unidade = unidade
            lote.save()

            Estoque.objects.create(
                lote_id=lote,
                funcionario_id=funcionario,
                tipo_movimentacao='Entrada',
                quantidade=quantidade,
                unidade=unidade,
                motivo=f"Entrada via nota fiscal {numero_nf or ''}".strip(),
                observacoes=f"Fornecedor: {fornecedor_nf}" if fornecedor_nf else None,
            )

            resultados.append({
                "tipo": "cultura",
                "descricao": descricao,
                "quantidade": quantidade,
                "unidade": unidade,
                "cultura_id": cultura.id,
                "cultura_nome": cultura.nome_cultura,
                "lote_id": lote.id,
                "lote_quantidade_atual": lote.quantidade,
                "cultura_criada": criou_cultura,
                "lote_criado": criou_lote,
            })

        return Response(
            {
                "mensagem": "Estoque atualizado com sucesso.",
                "numero_nf": numero_nf,
                "fornecedor": fornecedor_nf,
                "itens_processados": resultados,
            },
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _processar_insumo(descricao, quantidade, unidade, funcionario, numero_nf, fornecedor_nf):
        """
        Entrada de item classificado como insumo (fertilizante, defensivo,
        substrato etc). Nunca cria Cultura nem LotePlantio.
        """
        insumo, _criado = Insumo.objects.get_or_create(
            nome__iexact=descricao,
            defaults={
                'nome': descricao[:150],
                'unidade': unidade,
                'fornecedor': fornecedor_nf,
            },
        )
        insumo.quantidade_atual = (insumo.quantidade_atual or 0) + quantidade
        insumo.save()

        MovimentacaoInsumo.objects.create(
            insumo_id=insumo,
            funcionario_id=funcionario,
            tipo_movimentacao='Entrada',
            quantidade=quantidade,
            motivo=f"Entrada via nota fiscal {numero_nf or ''}".strip(),
            observacoes=f"Fornecedor: {fornecedor_nf}" if fornecedor_nf else None,
        )

        return {
            "tipo": "insumo",
            "descricao": descricao,
            "quantidade": quantidade,
            "unidade": unidade,
            "insumo_id": insumo.id,
            "insumo_nome": insumo.nome,
            "insumo_quantidade_atual": insumo.quantidade_atual,
        }

    @staticmethod
    def _parse_data(valor):
        if not valor:
            return date.today()
        try:
            return date.fromisoformat(valor)
        except (TypeError, ValueError):
            return date.today()

    @staticmethod
    def _encontrar_cultura(Cultura, descricao):
        cultura = Cultura.objects.filter(nome_cultura__iexact=descricao).first()
        if cultura:
            return cultura

        for candidata in Cultura.objects.all():
            nome = candidata.nome_cultura.strip().lower()
            desc = descricao.strip().lower()
            if nome and (nome in desc or desc in nome):
                return candidata
        return None

    @staticmethod
    def _criar_cultura_automatica(Cultura, descricao, numero_nf, fornecedor_nf):
        observacao = "Cultura criada automaticamente a partir da importação de nota fiscal"
        if numero_nf:
            observacao += f" nº {numero_nf}"
        if fornecedor_nf:
            observacao += f" (fornecedor: {fornecedor_nf})"

        return Cultura.objects.create(
            nome_cultura=descricao[:100],
            descricao="Cadastro automático — revisar e completar os dados desta cultura.",
            tempo_medio_colheita=0,
            temperatura_minima=0,
            temperatura_maxima=0,
            umidade_ideal=0,
            observacoes=observacao,
        )

    @staticmethod
    def _encontrar_lote_disponivel(LotePlantio, cultura):
        return LotePlantio.objects.filter(
            cultura_id=cultura,
            status__in=[LotePlantio.StatusPlantio.EM_ESTOQUE, LotePlantio.StatusPlantio.DISPONIVEL],
        ).order_by('-id').first()

    def _criar_lote_automatico(self, LotePlantio, Mesa, cultura, unidade, fornecedor_nf, data_emissao):
        mesa = Mesa.objects.filter(identificacao=self.MESA_PLACEHOLDER_ID).first()
        if not mesa:
            mesa = Mesa.objects.create(
                estufa=None,
                identificacao=self.MESA_PLACEHOLDER_ID,
                capacidade_maxima=0,
                status_mesa='reservada',
                observacoes="Mesa reservada automaticamente para lotes criados via importação de nota fiscal.",
            )

        return LotePlantio.objects.create(
            cultura_id=cultura,
            mesa_id=mesa,
            data_plantio=data_emissao or date.today(),
            status=LotePlantio.StatusPlantio.EM_ESTOQUE,
            quantidade=0,
            unidade=unidade,
            fornecedor=fornecedor_nf,
            validade=None,
        )