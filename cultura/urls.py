from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CulturaViewSet

router = DefaultRouter()
# /api/estoque/
router.register(r'cultura', CulturaViewSet)

urlpatterns = [
    path('', include(router.urls)),
]