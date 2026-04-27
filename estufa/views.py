from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from estufa.models import Estufa
from estufa.serializers import EstufaSerializer

class EstufaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Estufa.objects.all()
    serializer_class = EstufaSerializer