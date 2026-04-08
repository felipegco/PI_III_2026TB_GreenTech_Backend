from rest_framework import viewsets
from .models import Estufa
from .serializers import EstufaSerializer

class EstufaViewSet(viewsets.ModelViewSet):
    queryset = Estufa.objects.all() 
    serializer_class = EstufaSerializer