from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InsumoViewSet, ProdutoFinalViewSet

router = DefaultRouter()
# /api/estoque/insumos/
router.register(r'insumos', InsumoViewSet)
# /api/estoque/produtos/
router.register(r'produtos', ProdutoFinalViewSet)

urlpatterns = [
    path('', include(router.urls)),
]