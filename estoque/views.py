from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Estoque
from .serializers import EstoqueSerializer

class EstoqueViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Estoque.objects.all()
    serializer_class = EstoqueSerializer

