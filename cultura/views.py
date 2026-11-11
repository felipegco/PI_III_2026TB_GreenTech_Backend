from rest_framework import status, viewsets
from rest_framework.response import Response
from django.db.models import (Case, Count, ExpressionWrapper, F, FloatField, IntegerField, OuterRef, Subquery,
                              Sum, Value, When)
from django.db.models.functions import Coalesce

from lotePlantio.models import STATUS_EM_CULTIVO, LotePlantio
from .models import Cultura
from .serializers import CulturaSerializer


class CulturaViewSet(viewsets.ModelViewSet):
    serializer_class = CulturaSerializer

    def get_queryset(self):
        # Subqueries: um Count no mesmo join das colheitas multiplicaria as somas
        em_cultivo = LotePlantio.objects.filter(cultura_id=OuterRef('pk'), status__in=STATUS_EM_CULTIVO)
        mais_antigo = em_cultivo.order_by('data_plantio', 'id')
        queryset = Cultura.objects.annotate(
            lotes_ativos=Coalesce(Subquery(
                em_cultivo.order_by().values('cultura_id').annotate(n=Count('id')).values('n'),
                output_field=IntegerField(),
            ), 0),
            plantio_mais_antigo=Subquery(mais_antigo.values('data_plantio')[:1]),
            mesa_proxima_colheita=Subquery(mais_antigo.values('mesa_id__identificacao')[:1]),
        ).annotate(
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
