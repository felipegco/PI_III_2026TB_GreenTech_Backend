from rest_framework import viewsets
from colheita.models import Colheita
from colheita.serializers import ColheitaSerializer

class ColheitaViewSet(viewsets.ModelViewSet):
    queryset = Colheita.objects.all()
    serializer_class = ColheitaSerializer