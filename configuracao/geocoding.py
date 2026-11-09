"""Busca de cidades pela Geocoding API da Open-Meteo (gratuita, sem chave)."""
import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.core.cache import cache

logger = logging.getLogger(__name__)

URL_GEOCODING = 'https://geocoding-api.open-meteo.com/v1/search'
CACHE_SEGUNDOS = 24 * 60 * 60  # cidades não mudam de lugar


class GeocodingIndisponivel(Exception):
    pass


def buscar_cidades(termo, limite=8, pais='BR'):
    """Lista de cidades com nome, estado, país, coordenadas e fuso. Resultados ficam em cache por um dia."""
    termo = ' '.join(termo.split())
    # Hash do termo: chave curta e sem acentos, aceita por qualquer backend de cache
    chave = 'geocoding:' + hashlib.sha1(f'{pais}:{limite}:{termo.lower()}'.encode()).hexdigest()
    em_cache = cache.get(chave)
    if em_cache is not None:
        return em_cache

    parametros = {'name': termo, 'count': limite, 'language': 'pt', 'format': 'json'}
    if pais:
        parametros['countryCode'] = pais
    url = f'{URL_GEOCODING}?{urllib.parse.urlencode(parametros)}'
    try:
        with urllib.request.urlopen(url, timeout=8) as resposta:
            dados = json.loads(resposta.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError) as erro:
        logger.warning('Geocoding da Open-Meteo indisponível: %s', erro)
        raise GeocodingIndisponivel from erro

    cidades = [
        {
            'cidade': item.get('name', ''),
            'estado': item.get('admin1', ''),
            'pais': item.get('country', ''),
            'latitude': round(float(item['latitude']), 5),
            'longitude': round(float(item['longitude']), 5),
            'fuso_horario': item.get('timezone') or 'America/Sao_Paulo',
            'populacao': item.get('population'),
        }
        for item in dados.get('results') or []
        if 'latitude' in item and 'longitude' in item
    ]
    cache.set(chave, cidades, CACHE_SEGUNDOS)
    return cidades
