from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
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