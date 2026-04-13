from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('cliente.urls')),
    path('api/', include('colheita.urls')),
    path('api/estoque/', include('estoque.urls')),
    path('api/', include('estufa.urls')),
    path('api/', include('funcionarios.urls')),

]