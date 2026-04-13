from rest_framework import viewsets
from .models import Insumo, ProdutoFinal
from .serializers import InsumoSerializer, ProdutoFinalSerializer

class InsumoViewSet(viewsets.ModelViewSet):
    queryset = Insumo.objects.all()
    serializer_class = InsumoSerializer

class ProdutoFinalViewSet(viewsets.ModelViewSet):
    queryset = ProdutoFinal.objects.all()
    serializer_class = ProdutoFinalSerializer