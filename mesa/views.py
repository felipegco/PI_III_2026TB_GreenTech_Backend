from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Mesa
from .serializers import MesaSerializer

class MesaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Mesa.objects.all()
    serializer_class = MesaSerializer