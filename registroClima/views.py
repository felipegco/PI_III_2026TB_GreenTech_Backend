from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import RegistroClima
from .serializers import RegistroClimaSerializer

class RegistroClimaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = RegistroClima.objects.all()
    serializer_class = RegistroClimaSerializer