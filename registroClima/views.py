from rest_framework import viewsets
from .models import RegistroClima
from .serializers import RegistroClimaSerializer

class RegistroClimaViewSet(viewsets.ModelViewSet):
    queryset = RegistroClima.objects.all()
    serializer_class = RegistroClimaSerializer