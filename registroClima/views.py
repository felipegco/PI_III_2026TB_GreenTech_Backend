import hmac

from django.conf import settings
from django.db.models import OuterRef, Subquery
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import RegistroClima, RegistroIrrigacao
from .serializers import RegistroClimaSerializer, RegistroIrrigacaoSerializer

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
            serializer.save()
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