from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .geocoding import GeocodingIndisponivel, buscar_cidades
from .models import LocalizacaoPropriedade
from .serializers import LocalizacaoSerializer


def pode_configurar(usuario):
    return usuario.is_superuser or usuario.groups.filter(name__iregex=r'^(gerente|admin)$').exists()


class LocalizacaoView(APIView):
    """
    GET  /api/configuracao/localizacao/ → {configurada, pode_editar, localizacao}
    PUT  /api/configuracao/localizacao/ → grava a cidade (gerentes e administradores)
    """

    def resposta(self, request, localizacao, codigo=status.HTTP_200_OK):
        return Response({
            'configurada': localizacao is not None,
            'pode_editar': pode_configurar(request.user),
            'localizacao': LocalizacaoSerializer(localizacao).data if localizacao else None,
        }, status=codigo)

    def get(self, request):
        return self.resposta(request, LocalizacaoPropriedade.atual())

    def put(self, request):
        if not pode_configurar(request.user):
            return Response({'error': 'Só gerentes e administradores alteram a cidade da propriedade.'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = LocalizacaoSerializer(LocalizacaoPropriedade.atual(), data=request.data)
        serializer.is_valid(raise_exception=True)
        localizacao = serializer.save(pk=1, atualizado_por=request.user)
        return self.resposta(request, localizacao)


class BuscaCidadesView(APIView):
    """GET /api/configuracao/cidades/?q=mogi → cidades brasileiras com coordenadas (Open-Meteo)."""

    def get(self, request):
        termo = (request.query_params.get('q') or '').strip()
        if len(termo) < 3:
            return Response({'error': 'Digite pelo menos 3 letras do nome da cidade.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(buscar_cidades(termo))
        except GeocodingIndisponivel:
            return Response({'error': 'O serviço de busca de cidades não respondeu. Tente de novo em instantes.'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
