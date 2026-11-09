from django.urls import path

from .views import BuscaCidadesView, LocalizacaoView

urlpatterns = [
    path('configuracao/localizacao/', LocalizacaoView.as_view(), name='configuracao-localizacao'),
    path('configuracao/cidades/', BuscaCidadesView.as_view(), name='configuracao-cidades'),
]
