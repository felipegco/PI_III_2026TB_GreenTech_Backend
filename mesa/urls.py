from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MesaViewSet

router = DefaultRouter()
router.register(r'mesa', MesaViewSet)

urlpatterns = [
    path('', include(router.urls)),
]