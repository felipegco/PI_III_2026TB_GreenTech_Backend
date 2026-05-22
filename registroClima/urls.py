from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RegistroClimaViewSet, RegistroIrrigacaoViewSet

router = DefaultRouter()
router.register(r'clima', RegistroClimaViewSet)
router.register(r'irrigacao', RegistroIrrigacaoViewSet)

urlpatterns = [
    path('', include(router.urls)),
]