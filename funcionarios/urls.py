from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FuncionariosViewSet


router = DefaultRouter()
router.register(r'funcionarios', FuncionariosViewSet)

urlpatterns = [
    path('', include(router.urls)),
]