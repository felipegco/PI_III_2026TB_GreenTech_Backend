from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Pedido, PedidoItem
from .serializers import PedidoSerializer, PedidoItemSerializer

class PedidoViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Pedido.objects.all()
    serializer_class = PedidoSerializer

class PedidoItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = PedidoItem.objects.all()
    serializer_class = PedidoItemSerializer