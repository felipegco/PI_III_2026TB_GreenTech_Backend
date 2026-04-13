from rest_framework import viewsets
from .models import LotePlantio
from .serializers import ManejoSerializer

class ManejoViewSet(viewsets.ModelViewSet):
    queryset = LotePlantio.objects.all()
    serializer_class = ManejoSerializer