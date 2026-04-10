from rest_framework import viewsets
from .models import LotePlantio
from .serializers import LotePlantioSerializer

class LotePlantioViewSet(viewsets.ModelViewSet):
    queryset = LotePlantio.objects.all()
    serializer_class = LotePlantioSerializer