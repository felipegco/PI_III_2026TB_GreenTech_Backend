from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Alerta
from .serializers import AlertaSerializer

FILTROS = {'status': 'status', 'gravidade': 'gravidade', 'parametro': 'parametro', 'mesa': 'mesa_id'}


# Alertas são criados só pelo sistema, a partir das leituras; pela API dá para listar e resolver
class AlertaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Alerta.objects.select_related('mesa_id', 'leitura', 'resolvido_por')
    serializer_class = AlertaSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        for parametro_url, campo in FILTROS.items():
            valor = self.request.query_params.get(parametro_url)
            if valor:
                queryset = queryset.filter(**{campo: valor})
        return queryset

    @action(detail=True, methods=['patch'])
    def resolver(self, request, pk=None):
        alerta = self.get_object()
        if alerta.status == Alerta.Status.RESOLVIDO:
            return Response({'detail': 'Este alerta já foi resolvido.'}, status=status.HTTP_400_BAD_REQUEST)
        alerta.status = Alerta.Status.RESOLVIDO
        alerta.resolvido_em = timezone.now()
        alerta.resolvido_por = request.user
        alerta.save()
        return Response(self.get_serializer(alerta).data)
