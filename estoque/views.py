from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Insumo, ProdutoFinal
from .serializers import InsumoSerializer, ProdutoFinalSerializer

class InsumoViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Insumo.objects.all()
    serializer_class = InsumoSerializer

class ProdutoFinalViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = ProdutoFinal.objects.all()
    serializer_class = ProdutoFinalSerializer