from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import LotePlantio
from .serializers import LotePlantioSerializer

class LotePlantioViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = LotePlantio.objects.all()
    serializer_class = LotePlantioSerializer