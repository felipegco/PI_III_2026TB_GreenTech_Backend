from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ColheitaViewSet


router = DefaultRouter()
router.register(r'colheita', ColheitaViewSet)

urlpatterns = [
    path('', include(router.urls)),
]