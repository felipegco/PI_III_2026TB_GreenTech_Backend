import json
import random
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from configuracao.previsao import previsao_chuva
from mesa.models import Mesa
from registroClima.ia.servico import PREFIXO_IA, decidir_mesa, muda_a_valvula
from registroClima.models import ModoIrrigacao, RegistroClima, RegistroIrrigacao
from registroClima.simulacao import PREFIXO_SIMULADO, enviar_para_api

# Histerese: abre abaixo do mínimo, fecha acima do máximo e mantém o estado entre os dois,
# para a válvula não ficar abrindo e fechando a cada leitura
SOLO_ABRE_ABAIXO_DE = 40.0
SOLO_FECHA_ACIMA_DE = 65.0

# ia: árvore de decisão (RF10), respeitando o modo manual/automático do sistema
# regra: histerese fixa 40 %/65 %, a lógica anterior à IA
MODOS = ['ia', 'regra', 'abrir', 'fechar']


def valvula_da_mesa(mesa):
    """Reaproveita a válvula já registrada para a mesa; senão usa VLV-<id da mesa>."""
    ultimo = RegistroIrrigacao.objects.filter(mesa_id=mesa).order_by('-data_registro', '-id').first()
    return ultimo.valvula_id if ultimo else f'VLV-{mesa.id:02d}'


def estado_atual(mesa):
    """Último estado conhecido da válvula ('ativa'/'inativa') e a última umidade do solo lida."""
    ultimo = RegistroIrrigacao.objects.filter(mesa_id=mesa).order_by('-data_registro', '-id').first()
    leitura = (
        RegistroClima.objects.filter(mesa_id=mesa, umidade_solo__isnull=False)
        .order_by('-data_registro', '-id').first()
    )
    return (
        ultimo.status_atual if ultimo else 'inativa',
        float(leitura.umidade_solo) if leitura else None,
    )


def decidir(umidade_solo, status_anterior, modo='regra'):
    """Devolve (novo_status, motivo) a partir da umidade do solo e do estado anterior."""
    if modo == 'abrir':
        return 'ativa', 'abertura forçada no simulador'
    if modo == 'fechar':
        return 'inativa', 'fechamento forçado no simulador'
    if umidade_solo is None:
        return 'inativa', 'sem leitura de umidade do solo, válvula mantida fechada'
    if umidade_solo < SOLO_ABRE_ABAIXO_DE:
        return 'ativa', f'solo em {umidade_solo:.1f} %, abaixo de {SOLO_ABRE_ABAIXO_DE:.0f} %'
    if umidade_solo > SOLO_FECHA_ACIMA_DE:
        return 'inativa', f'solo em {umidade_solo:.1f} %, acima de {SOLO_FECHA_ACIMA_DE:.0f} %'
    return status_anterior, f'solo em {umidade_solo:.1f} %, dentro da faixa, estado mantido'


def decidir_pela_ia(mesa, status_anterior, previsao):
    """
    Grava a decisão da árvore e devolve (novo_status, motivo, decisao). No modo automático a válvula
    segue a IA; no manual a IA só sugere e a válvula fica como está.
    """
    decisao = decidir_mesa(mesa, executar=False, previsao=previsao)
    if decisao is None:
        return status_anterior, 'sem leitura de umidade do solo, válvula mantida', None
    rotulo = f'{decisao.get_acao_display()} ({float(decisao.confianca):.0%})'
    if decisao.modo == ModoIrrigacao.Modo.AUTOMATICO_IA:
        return ('ativa' if decisao.irrigar else 'inativa'), f'{PREFIXO_IA} {rotulo}. {decisao.justificativa}', decisao
    return status_anterior, f'{PREFIXO_IA} sugere {rotulo}; modo manual, válvula mantida.', decisao


def gerar_registro(mesa_id, valvula_id, status, motivo, duracao_min, rng=random):
    """Monta o payload no formato aceito por /api/irrigacao/atualizar_status/."""
    fluxo = round(rng.uniform(6, 10), 2) if status == 'ativa' else 0.0
    return {
        'mesa_id': mesa_id,
        'valvula_id': valvula_id,
        'status_atual': status,
        'fluxo_l_min': fluxo,
        'consumo_ciclo_l': round(fluxo * duracao_min, 2),
        'simulado': True,
        'observacoes': f'{PREFIXO_SIMULADO} {motivo}'[:1000],
    }


class Command(BaseCommand):
    help = (
        'Simula o controlador das válvulas de irrigação: lê a última umidade do solo de cada mesa, '
        'decide abrir ou fechar e envia para /api/irrigacao/atualizar_status/ com a chave de API.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--url', default='http://localhost:8000', help='Endereço base da API.')
        parser.add_argument('--mesa', type=int, action='append', dest='mesas',
                            help='ID da mesa (pode repetir). Padrão: todas as mesas.')
        parser.add_argument('--modo', choices=MODOS, default='ia',
                            help='ia decide pela árvore de decisão (respeita o modo manual/automático do sistema); '
                                 'regra usa a histerese fixa de 40 %%/65 %%; abrir/fechar forçam o estado.')
        parser.add_argument('--duracao', type=float, default=5.0,
                            help='Minutos de cada ciclo, usado no cálculo do consumo.')
        parser.add_argument('--ciclos', type=int, default=1, help='Quantas rodadas enviar. 0 = sem fim.')
        parser.add_argument('--intervalo', type=float, default=5.0, help='Segundos entre as rodadas.')
        parser.add_argument('--api-key', default=None, help='Padrão: variável de ambiente IOT_API_KEY.')
        parser.add_argument('--seed', type=int, default=None, help='Semente para registros reproduzíveis.')
        parser.add_argument('--dry-run', action='store_true', help='Só mostra os registros, sem enviar.')

    def handle(self, *args, **opts):
        api_key = opts['api_key'] or settings.IOT_API_KEY
        if not api_key and not opts['dry_run']:
            raise CommandError('Defina IOT_API_KEY no ambiente ou passe --api-key.')

        mesas = Mesa.objects.filter(estufa__isnull=False)
        if opts['mesas']:
            mesas = mesas.filter(id__in=opts['mesas'])
        mesas = list(mesas.order_by('id'))
        if not mesas:
            raise CommandError('Nenhuma mesa encontrada. Cadastre estufas e mesas antes de simular.')

        rng = random.Random(opts['seed'])
        endpoint = opts['url'].rstrip('/') + '/api/irrigacao/atualizar_status/'
        ciclo = 0

        try:
            while opts['ciclos'] == 0 or ciclo < opts['ciclos']:
                ciclo += 1
                # A previsão de chuva vale para todas as mesas: consulta uma vez por rodada
                previsao = previsao_chuva() if opts['modo'] == 'ia' else None
                for mesa in mesas:
                    # No dry run as decisões da IA são desfeitas no fim: nada fica gravado
                    with transaction.atomic():
                        status_anterior, umidade_solo = estado_atual(mesa)
                        decisao = None
                        if opts['modo'] == 'ia':
                            status, motivo, decisao = decidir_pela_ia(mesa, status_anterior, previsao)
                            if decisao is None:
                                # Mesa sem sensor de solo (ex.: hidroponia) não tem válvula para a IA comandar
                                self.stdout.write(f'{mesa.identificacao}: sem leitura de umidade do solo, ignorada.')
                                continue
                        else:
                            status, motivo = decidir(umidade_solo, status_anterior, opts['modo'])
                        registro = gerar_registro(
                            mesa.id, valvula_da_mesa(mesa), status, motivo, opts['duracao'], rng,
                        )
                        if opts['dry_run']:
                            self.stdout.write(json.dumps(registro, ensure_ascii=False))
                            transaction.set_rollback(True)
                        elif self._enviar(endpoint, api_key, registro, mesa) and decisao is not None:
                            self._vincular(decisao, status_anterior, status)
                if opts['ciclos'] == 0 or ciclo < opts['ciclos']:
                    time.sleep(opts['intervalo'])
        except KeyboardInterrupt:
            self.stdout.write('\nSimulação interrompida.')

    def _vincular(self, decisao, status_anterior, status):
        """A válvula obedeceu a IA (modo automático, estado mudou): marca a decisão como executada."""
        if muda_a_valvula(decisao) and status != status_anterior:
            decisao.registro_irrigacao = (
                RegistroIrrigacao.objects.filter(mesa_id=decisao.mesa_id).order_by('-data_registro', '-id').first()
            )
            decisao.executada = True
            decisao.save(update_fields=['registro_irrigacao', 'executada'])

    def _enviar(self, endpoint, api_key, registro, mesa):
        codigo, corpo = enviar_para_api(endpoint, api_key, registro)
        if codigo == 201:
            self.stdout.write(self.style.SUCCESS(
                f'[{codigo}] {mesa.identificacao} {registro["valvula_id"]}: {registro["status_atual"]}, '
                f'{registro["fluxo_l_min"]} L/min, {registro["consumo_ciclo_l"]} L'
            ))
            return True
        self.stderr.write(self.style.ERROR(f'[{codigo}] {mesa.identificacao}: {corpo}'))
        return False
