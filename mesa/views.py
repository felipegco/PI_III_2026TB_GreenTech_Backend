from django.db import transaction
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Mesa
from .serializers import MesaSerializer


class MesaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Mesa.objects.all()
    serializer_class = MesaSerializer

    # atomic: o select_for_update do serializer só tem efeito dentro de uma transação.
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
