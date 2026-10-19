import json
import random
import time
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from lotePlantio.models import LotePlantio
from mesa.models import Mesa

# Faixa usada quando a mesa não tem lote ativo com cultura vinculada
FAIXA_PADRAO = {'temp_min': 16.0, 'temp_max': 30.0, 'umidade_ideal': 70.0}

CENARIOS = ['normal', 'calor', 'frio', 'ar_seco', 'solo_seco', 'aleatorio']


def faixa_da_mesa(mesa):
    """Limites da cultura do lote ativo mais recente na mesa, ou a faixa padrão."""
    lote = (
        LotePlantio.objects.filter(mesa_id=mesa, status=LotePlantio.StatusPlantio.ATIVO)
        .select_related('cultura_id')
        .order_by('-data_plantio')
        .first()
    )
    if not lote:
        return FAIXA_PADRAO
    cultura = lote.cultura_id
    return {
        'temp_min': float(cultura.temperatura_minima),
        'temp_max': float(cultura.temperatura_maxima),
        'umidade_ideal': float(cultura.umidade_ideal),
    }


def gerar_leitura(mesa_id, faixa, cenario, rng=random):
    """Monta o payload de uma leitura no formato aceito por /api/clima/receber_dados_iot/."""
    if cenario == 'aleatorio':
        # Na maior parte do tempo tudo normal; às vezes uma anomalia para gerar alertas
        cenario = rng.choices(['normal', 'calor', 'frio', 'ar_seco', 'solo_seco'], [80, 5, 5, 5, 5])[0]

    temp_min, temp_max = faixa['temp_min'], faixa['temp_max']
    umidade_ideal = faixa['umidade_ideal']

    temperatura = rng.uniform(temp_min + 1, temp_max - 1)
    umidade = min(max(rng.uniform(umidade_ideal - 5, umidade_ideal + 5), 0), 100)
    umidade_solo = rng.uniform(45, 75)

    if cenario == 'calor':
        temperatura = temp_max + rng.uniform(3, 8)
    elif cenario == 'frio':
        temperatura = temp_min - rng.uniform(3, 6)
    elif cenario == 'ar_seco':
        umidade = rng.uniform(25, 40)
    elif cenario == 'solo_seco':
        umidade_solo = rng.uniform(10, 25)

    return {
        'mesa_id': mesa_id,
        'temperatura': round(temperatura, 2),
        'umidade': round(umidade, 2),
        'luminosidade': round(rng.uniform(15000, 45000), 2),
        'ventilacao': rng.randint(20, 60),
        'umidade_solo': round(umidade_solo, 2),
        'co2': round(rng.uniform(400, 900), 2),
        'ph': round(rng.uniform(5.8, 6.8), 2),
        'observacoes': f'Leitura simulada ({cenario})',
    }


class Command(BaseCommand):
    help = (
        'Simula os sensores das estufas enviando leituras para /api/clima/receber_dados_iot/, '
        'com a mesma autenticação por chave de API que um microcontrolador usaria.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--url', default='http://localhost:8000', help='Endereço base da API.')
        parser.add_argument('--mesa', type=int, action='append', dest='mesas',
                            help='ID da mesa (pode repetir). Padrão: todas as mesas.')
        parser.add_argument('--cenario', choices=CENARIOS, default='normal')
        parser.add_argument('--ciclos', type=int, default=1, help='Quantas rodadas enviar. 0 = sem fim.')
        parser.add_argument('--intervalo', type=float, default=5.0, help='Segundos entre as rodadas.')
        parser.add_argument('--api-key', default=None, help='Padrão: variável de ambiente IOT_API_KEY.')
        parser.add_argument('--seed', type=int, default=None, help='Semente para leituras reproduzíveis.')
        parser.add_argument('--dry-run', action='store_true', help='Só mostra as leituras, sem enviar.')

    def handle(self, *args, **opts):
        api_key = opts['api_key'] or settings.IOT_API_KEY
        if not api_key and not opts['dry_run']:
            raise CommandError('Defina IOT_API_KEY no ambiente ou passe --api-key.')

        mesas = Mesa.objects.all()
        if opts['mesas']:
            mesas = mesas.filter(id__in=opts['mesas'])
        mesas = list(mesas.order_by('id'))
        if not mesas:
            raise CommandError('Nenhuma mesa encontrada. Cadastre estufas e mesas antes de simular.')

        rng = random.Random(opts['seed'])
        endpoint = opts['url'].rstrip('/') + '/api/clima/receber_dados_iot/'
        ciclo = 0

        try:
            while opts['ciclos'] == 0 or ciclo < opts['ciclos']:
                ciclo += 1
                for mesa in mesas:
                    leitura = gerar_leitura(mesa.id, faixa_da_mesa(mesa), opts['cenario'], rng)
                    if opts['dry_run']:
                        self.stdout.write(json.dumps(leitura, ensure_ascii=False))
                    else:
                        self._enviar(endpoint, api_key, leitura, mesa)
                if opts['ciclos'] == 0 or ciclo < opts['ciclos']:
                    time.sleep(opts['intervalo'])
        except KeyboardInterrupt:
            self.stdout.write('\nSimulação interrompida.')

    def _enviar(self, endpoint, api_key, leitura, mesa):
        requisicao = urllib.request.Request(
            endpoint,
            data=json.dumps(leitura).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': f'Api-Key {api_key}'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(requisicao, timeout=10) as resposta:
                self.stdout.write(self.style.SUCCESS(
                    f'[{resposta.status}] {mesa.identificacao}: {leitura["temperatura"]} °C, '
                    f'umidade {leitura["umidade"]} %, solo {leitura["umidade_solo"]} %'
                ))
        except urllib.error.HTTPError as erro:
            corpo = erro.read().decode(errors='replace')
            self.stderr.write(self.style.ERROR(f'[{erro.code}] {mesa.identificacao}: {corpo}'))
        except urllib.error.URLError as erro:
            raise CommandError(f'Não foi possível conectar em {endpoint}: {erro.reason}')
