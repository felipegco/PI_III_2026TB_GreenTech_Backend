from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from colheita.models import Colheita
from colheita.serializers import ColheitaSerializer

class ColheitaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Colheita.objects.all()
    serializer_class = ColheitaSerializer