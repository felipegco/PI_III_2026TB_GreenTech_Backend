import json
import random
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from alerta.services import FAIXA_PADRAO, faixa_da_mesa as faixa_e_origem_da_mesa
from mesa.models import Mesa
from registroClima.simulacao import PREFIXO_SIMULADO, enviar_para_api

CENARIOS = ['normal', 'calor', 'frio', 'ar_seco', 'solo_seco', 'aleatorio']


def faixa_da_mesa(mesa):
    """Mesma faixa usada na geração de alertas, para o cenário normal não disparar alertas."""
    return faixa_e_origem_da_mesa(mesa)[0]


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
        'simulado': True,
        'observacoes': f'{PREFIXO_SIMULADO} Leitura gerada pelo simulador (cenário {cenario})',
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
        codigo, corpo = enviar_para_api(endpoint, api_key, leitura)
        if codigo == 201:
            self.stdout.write(self.style.SUCCESS(
                f'[{codigo}] {mesa.identificacao}: {leitura["temperatura"]} °C, '
                f'umidade {leitura["umidade"]} %, solo {leitura["umidade_solo"]} %'
            ))
        else:
            self.stderr.write(self.style.ERROR(f'[{codigo}] {mesa.identificacao}: {corpo}'))
