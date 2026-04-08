from django.contrib import admin
from django.urls import path, include # Adicionamos o include aqui!

urlpatterns = [
    path('admin/', admin.site.urls),
    # Tudo o que começar com 'api/infra/' vai ser mandado para o nosso arquivo novo
    path('api/infra/', include('infraestrutura.urls')), 
]