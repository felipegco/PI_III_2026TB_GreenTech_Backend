from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import RegistroClima, RegistroIrrigacao
from .serializers import RegistroClimaSerializer, RegistroIrrigacaoSerializer

# Permissão por API Key estática para evitar expiração de JWT nos microcontroladores
class HasAPIKey(BasePermission):
    def has_permission(self, request, view):
        api_key = request.headers.get('Authorization')
        return api_key == "Api-Key GT_IOT_SECRET_KEY_2026"

class RegistroClimaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = RegistroClima.objects.all()
    serializer_class = RegistroClimaSerializer

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