from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InsumoViewSet, MovimentacaoInsumoViewSet

router = DefaultRouter()
router.register(r'insumos', InsumoViewSet)
router.register(r'movimentacoes-insumo', MovimentacaoInsumoViewSet)

urlpatterns = [
    path('', include(router.urls)),
]