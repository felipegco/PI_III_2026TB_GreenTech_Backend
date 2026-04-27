from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from cliente.models import Cliente
from cliente.serializers import ClienteSerializer

class ClienteViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer