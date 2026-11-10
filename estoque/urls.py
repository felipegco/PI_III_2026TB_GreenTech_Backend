from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EstoqueViewSet, OcrNotaFiscalView, ConfirmarLoteNfView
from insumo.views import PrevisaoEstoqueView

router = DefaultRouter()
# /api/estoque/
router.register(r'estoque', EstoqueViewSet)

urlpatterns = [
    # /api/estoque/ocr-nota-fiscal/
    path('estoque/ocr-nota-fiscal/', OcrNotaFiscalView.as_view(), name='estoque-ocr-nota-fiscal'),
    # /api/estoque/confirmar-lote-nf/
    path('estoque/confirmar-lote-nf/', ConfirmarLoteNfView.as_view(), name='estoque-confirmar-lote-nf'),
    # /api/estoque/previsao-prophet/ (RF09)
    path('estoque/previsao-prophet/', PrevisaoEstoqueView.as_view(), name='estoque-previsao-prophet'),
    path('', include(router.urls)),
]