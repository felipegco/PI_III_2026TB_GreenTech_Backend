from rest_framework import viewsets
from estufa.models import Estufa
from estufa.serializers import EstufaSerializer

class EstufaViewSet(viewsets.ModelViewSet):
    queryset = Estufa.objects.all()
    serializer_class = EstufaSerializer