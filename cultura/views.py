from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Cultura
from .serializers import CulturaSerializer

class CulturaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Cultura.objects.all()
    serializer_class = CulturaSerializer


