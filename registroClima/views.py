import hmac

from django.conf import settings
from django.db.models import OuterRef, Subquery
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.decorators import action
from alerta.services import gerar_alertas
from configuracao.models import LocalizacaoPropriedade
from configuracao.previsao import previsao_chuva
from configuracao.views import pode_configurar
from mesa.models import Mesa
from .ia.servico import decidir_todas, ultima_leitura_com_solo, valvula_da_mesa
from .models import DecisaoIrrigacao, ModoIrrigacao, RegistroClima, RegistroIrrigacao
from .serializers import (
    DecisaoIrrigacaoSerializer, ModoIrrigacaoSerializer, RegistroClimaSerializer, RegistroIrrigacaoSerializer,
)

LIMITE_DECISOES_PADRAO = 50
LIMITE_DECISOES_MAXIMO = 200

API_KEY_PREFIX = 'Api-Key '

# Permissão por API Key para evitar expiração de JWT nos microcontroladores.
# A chave vem da variável de ambiente IOT_API_KEY; sem ela configurada, a ingestão fica bloqueada.
class HasAPIKey(BasePermission):
    def has_permission(self, request, view):
        chave_esperada = settings.IOT_API_KEY
        cabecalho = request.headers.get('Authorization', '')
        if not chave_esperada or not cabecalho.startswith(API_KEY_PREFIX):
            return False
        chave_recebida = cabecalho[len(API_KEY_PREFIX):]
        return hmac.compare_digest(chave_recebida.encode(), chave_esperada.encode())

class RegistroClimaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = RegistroClima.objects.all()
    serializer_class = RegistroClimaSerializer

    def perform_create(self, serializer):
        # Toda leitura nova, manual ou dos sensores, passa pela verificação de alertas
        gerar_alertas(serializer.save())

    @action(detail=False, methods=['get'])
    def ultimas(self, request):
        """Leitura mais recente de cada mesa, para o dashboard em tempo real."""
        mais_recente_da_mesa = RegistroClima.objects.filter(
            mesa_id=OuterRef('mesa_id')
        ).order_by('-data_registro', '-id').values('id')[:1]
        leituras = RegistroClima.objects.filter(id=Subquery(mais_recente_da_mesa))
        return Response(self.get_serializer(leituras, many=True).data)

    @action(detail=False, methods=['post'], permission_classes=[HasAPIKey])
    def receber_dados_iot(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            return Response({"status": "Dados de clima registrados com sucesso!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RegistroIrrigacaoViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = RegistroIrrigacao.objects.all()
    serializer_class = RegistroIrrigacaoSerializer

    @action(detail=False, methods=['post'], permission_classes=[HasAPIKey])
    def atualizar_status(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"status": "Telemetria de irrigação atualizada com sucesso!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # --- Irrigação inteligente (RF10). detail=False: sem isso o router trataria "status" como id ---

    @action(detail=False, methods=['get'])
    def status(self, request):
        """Modo atual, previsão de chuva usada pela IA e a situação de cada válvula com a última decisão."""
        modo = ModoIrrigacao.atual()
        valvulas = []
        for mesa in Mesa.objects.filter(estufa__isnull=False).select_related('estufa').order_by('id'):
            valvula_id, ultimo = valvula_da_mesa(mesa)
            leitura = ultima_leitura_com_solo(mesa)
            decisao = DecisaoIrrigacao.objects.filter(mesa_id=mesa).first()
            valvulas.append({
                'valvula_id': valvula_id,
                'mesa_id': mesa.id,
                'mesa': mesa.identificacao,
                'estufa': mesa.estufa.nome_setor,
                'status_atual': ultimo.status_atual if ultimo else 'inativa',
                'desde': ultimo.data_registro if ultimo else None,
                'umidade_solo': float(leitura.umidade_solo) if leitura else None,
                'ultima_decisao': DecisaoIrrigacaoSerializer(decisao).data if decisao else None,
            })
        return Response({
            'modo': modo.modo,
            'modo_nome': modo.get_modo_display(),
            'modo_atualizado_em': modo.atualizado_em,
            'pode_alterar_modo': pode_configurar(request.user),
            'localizacao_configurada': LocalizacaoPropriedade.atual() is not None,
            'previsao_chuva': previsao_chuva().para_dict(),
            'valvulas': valvulas,
        })

    @action(detail=False, methods=['get'], url_path='decisoes-ia')
    def decisoes_ia(self, request):
        """
        Decisões mais recentes da IA. Filtros: ?mesa=<id>, ?limite=<n> (padrão 50, máximo 200) e
        ?so_mudancas=1 (só abrir e fechar, sem os "manter" de cada leitura).
        """
        decisoes = DecisaoIrrigacao.objects.select_related('mesa_id')
        if request.query_params.get('so_mudancas') in ('1', 'true'):
            decisoes = decisoes.filter(acao__in=[DecisaoIrrigacao.Acao.ABRIR, DecisaoIrrigacao.Acao.FECHAR])
        mesa = request.query_params.get('mesa')
        if mesa:
            if not mesa.isdigit():
                return Response({'error': 'mesa deve ser o id numérico da mesa.'}, status=status.HTTP_400_BAD_REQUEST)
            decisoes = decisoes.filter(mesa_id=int(mesa))
        try:
            limite = int(request.query_params.get('limite', LIMITE_DECISOES_PADRAO))
        except ValueError:
            limite = LIMITE_DECISOES_PADRAO
        limite = max(1, min(limite, LIMITE_DECISOES_MAXIMO))
        return Response(DecisaoIrrigacaoSerializer(decisoes[:limite], many=True).data)

    @action(detail=False, methods=['post'])
    def modo(self, request):
        """Troca entre MANUAL (IA só sugere) e AUTOMATICO_IA (IA aciona as válvulas). Gerentes e admins."""
        if not pode_configurar(request.user):
            return Response({'error': 'Só gerentes e administradores alteram o modo de irrigação.'},
                            status=status.HTTP_403_FORBIDDEN)
        entrada = ModoIrrigacaoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        modo = ModoIrrigacao.atual()
        modo.modo = entrada.validated_data['modo']
        modo.atualizado_por = request.user
        modo.save()
        return Response({'modo': modo.modo, 'modo_nome': modo.get_modo_display()})

    @action(detail=False, methods=['post'])
    def avaliar(self, request):
        """Roda a árvore agora para todas as mesas. No automático, abre e fecha as válvulas. Gerentes e admins."""
        if not pode_configurar(request.user):
            return Response({'error': 'Só gerentes e administradores disparam a avaliação da irrigação.'},
                            status=status.HTTP_403_FORBIDDEN)
        decisoes = decidir_todas()
        return Response(DecisaoIrrigacaoSerializer(decisoes, many=True).data, status=status.HTTP_201_CREATED)
