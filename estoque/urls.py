from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EstoqueViewSet

router = DefaultRouter()
# /api/estoque/
router.register(r'estoque', EstoqueViewSet)

urlpatterns = [
    path('', include(router.urls)),
]