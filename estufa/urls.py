from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EstufaViewSet


router = DefaultRouter()
router.register(r'estufa', EstufaViewSet)

urlpatterns = [
    path('', include(router.urls)),
]