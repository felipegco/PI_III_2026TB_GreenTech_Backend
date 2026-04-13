from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PedidoViewSet, PedidoItemViewSet

router = DefaultRouter()
router.register(r'pedido', PedidoViewSet)
router.register(r'pedido-item', PedidoItemViewSet)

urlpatterns = [
    path('', include(router.urls)),
]