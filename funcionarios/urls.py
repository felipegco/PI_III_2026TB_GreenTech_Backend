from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import FuncionariosViewSet, LogoutView, AuditoriaGeralView

router = DefaultRouter()
router.register(r'funcionarios', FuncionariosViewSet)

# funcionarios/urls.py
urlpatterns = [
    path('funcionarios/auditoria/', AuditoriaGeralView.as_view(), name='auditoria-geral'),
    path('', include(router.urls)),

    # 3. ROTAS DE AUTENTICAÇÃO
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),   # era 'login/'
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='auth_logout'),
]