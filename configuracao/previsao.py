"""
Previsão de chuva das próximas horas na cidade da propriedade (Open-Meteo, sem chave).

Entrada da árvore de decisão da irrigação (RF10): com chuva suficiente prevista, a válvula
fica fechada e a água da chuva repõe o solo. Se a cidade não estiver configurada ou o serviço
não responder, a previsão vale 0 mm: a irrigação segue só pelos sensores, nunca trava.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass

from django.core.cache import cache

from .models import LocalizacaoPropriedade

logger = logging.getLogger(__name__)

URL_PREVISAO = 'https://api.open-meteo.com/v1/forecast'
HORAS_PADRAO = 6
CACHE_SEGUNDOS = 60 * 60  # a Open-Meteo atualiza o modelo de hora em hora


@dataclass
class PrevisaoChuva:
    chuva_mm: float
    probabilidade_max: int | None
    horas: int
    disponivel: bool
    cidade: str | None
    motivo: str = ''

    def para_dict(self):
        return asdict(self)


def _consultar(latitude, longitude, fuso, horas):
    parametros = {
        'latitude': latitude,
        'longitude': longitude,
        'hourly': 'precipitation,precipitation_probability',
        'forecast_hours': horas,
        'timezone': fuso or 'America/Sao_Paulo',
    }
    url = f'{URL_PREVISAO}?{urllib.parse.urlencode(parametros)}'
    with urllib.request.urlopen(url, timeout=8) as resposta:
        dados = json.loads(resposta.read().decode())
    horario = dados.get('hourly') or {}
    chuva = [v for v in horario.get('precipitation') or [] if v is not None][:horas]
    probabilidade = [v for v in horario.get('precipitation_probability') or [] if v is not None][:horas]
    if not chuva:
        raise ValueError('resposta sem precipitação horária')
    return round(float(sum(chuva)), 1), (int(max(probabilidade)) if probabilidade else None)


def previsao_chuva(horas=HORAS_PADRAO, localizacao=None):
    """Chuva somada nas próximas `horas` na cidade configurada. Resultado em cache por uma hora."""
    localizacao = localizacao or LocalizacaoPropriedade.atual()
    if localizacao is None:
        return PrevisaoChuva(0.0, None, horas, False, None,
                             'Cidade da propriedade não configurada; previsão de chuva considerada 0 mm.')

    cidade = str(localizacao)
    chave = f'previsao_chuva:{localizacao.latitude}:{localizacao.longitude}:{horas}'
    em_cache = cache.get(chave)
    if em_cache is not None:
        return PrevisaoChuva(**em_cache)

    try:
        chuva_mm, probabilidade = _consultar(
            localizacao.latitude, localizacao.longitude, localizacao.fuso_horario, horas,
        )
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as erro:
        logger.warning('Previsão de chuva da Open-Meteo indisponível: %s', erro)
        # Sem cache da falha: a próxima decisão tenta de novo
        return PrevisaoChuva(0.0, None, horas, False, cidade,
                             'Serviço de previsão não respondeu; previsão de chuva considerada 0 mm.')

    previsao = PrevisaoChuva(chuva_mm, probabilidade, horas, True, cidade)
    cache.set(chave, previsao.para_dict(), CACHE_SEGUNDOS)
    return previsao
