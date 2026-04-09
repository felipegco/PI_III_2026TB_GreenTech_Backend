from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LotePlantioViewSet

router = DefaultRouter()
router.register(r'lotes', LotePlantioViewSet)

urlpatterns = [
    path('', include(router.urls)),
]