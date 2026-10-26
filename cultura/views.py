from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, F, FloatField, ExpressionWrapper, Case, When, Value
from django.db.models.functions import Coalesce

from .models import Cultura
from .serializers import CulturaSerializer


class CulturaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = CulturaSerializer

    def get_queryset(self):
        queryset = Cultura.objects.annotate(
            total_colhido=Coalesce(
                Sum('lotes_plantio__colheita__quantidade_colhida'),
                0.0,
                output_field=FloatField()
            ),
            total_perda=Coalesce(
                Sum('lotes_plantio__colheita__quantidade_perda'),
                0.0,
                output_field=FloatField()
            )
        ).annotate(
            total_geral=F('total_colhido') + F('total_perda')
        ).annotate(
            taxa_producao=Case(
                When(
                    total_geral__gt=0,
                    then=ExpressionWrapper(
                        (F('total_colhido') * 100.0) / F('total_geral'),
                        output_field=FloatField()
                    )
                ),
                default=Value(0.0),
                output_field=FloatField()
            )
        )

        return queryset

    def destroy(self, request, *args, **kwargs):
        cultura = self.get_object()
        total = cultura.lotes_plantio.count()
        if total:
            return Response(
                {"error": f'"{cultura}" tem {total} lote(s) registrados. Excluir apagaria colheitas e '
                          f'movimentações do histórico; edite a cultura em vez de excluir.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)
