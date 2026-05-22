from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.decorators import action
from django.conf import settings
from .models import RegistroClima
from .serializers import RegistroClimaSerializer

# Permissão customizada para o Sensor IoT
class HasAPIKey(BasePermission):
    def has_permission(self, request, view):
        # O ESP32 deve mandar um cabeçalho: "Authorization: [TOKEN]"
        api_key = request.headers.get('Authorization')
        # ********** Em produção, colocar essa chave no .env do Django (settings.py) **********
        return api_key == "Api-Key GT_IOT_SECRET_KEY_2026"

class RegistroClimaViewSet(viewsets.ModelViewSet):
    # Por padrão, exige login de usuário humano
    permission_classes = [IsAuthenticated]
    queryset = RegistroClima.objects.all()
    serializer_class = RegistroClimaSerializer

   #Futuramente será um protocolo MQTT
    @action(detail=False, methods=['post'], permission_classes=[HasAPIKey])
    def receber_dados_iot(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"status": "Dados registrados com sucesso!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)