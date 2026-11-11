"""
Previsão de fim de estoque dos insumos (RF09).

Para cada insumo monta a série diária de consumo (Saída + Perda) e projeta os próximos dias:
- Prophet, quando há histórico suficiente: separa tendência e sazonalidade semanal, então um
  consumo em alta antecipa a data de esgotamento;
- média móvel dos últimos dias, como contingência para histórico curto ou Prophet indisponível;
- sem consumo, quando o insumo nunca saiu do estoque (não há como estimar).

A data de esgotamento é o primeiro dia em que o consumo previsto acumulado alcança o saldo atual.
O resultado fica em PrevisaoEstoque e só é recalculado quando o insumo se movimenta ou o dia vira.
"""
import logging
from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Max, Q
from django.utils import timezone

from .models import Insumo, PrevisaoEstoque

JANELA_DIAS = 180            # histórico usado no ajuste
HORIZONTE_DIAS = 365         # até onde a previsão procura o esgotamento
MIN_DIAS_PROPHET = 14        # menos que isso vira média móvel (card RF09)
MIN_CONSUMOS_PROPHET = 5     # dias com consumo registrado
JANELA_MEDIA_MOVEL = 28
JANELA_PERCENTUAL = 90       # o percentual compara o saldo com o maior saldo desse período

CONSUMO = Q(tipo_movimentacao__iexact='saída') | Q(tipo_movimentacao__iexact='saida') | \
    Q(tipo_movimentacao__iexact='perda')
ENTRADAS = ('ENTRADA', 'AJUSTE')

logger = logging.getLogger(__name__)


@dataclass
class Projecao:
    modelo: str
    consumo_diario: list          # consumo previsto para amanhã, depois de amanhã, ...
    dias_historico: int
    observacao: str = ''


def _dia_local(momento):
    return timezone.localtime(momento).date()


def serie_consumo(insumo, hoje=None):
    """{data: consumo} de todos os dias desde a primeira movimentação (até JANELA_DIAS), zeros inclusos."""
    hoje = hoje or timezone.localdate()
    inicio_janela = hoje - timedelta(days=JANELA_DIAS - 1)
    movimentos = insumo.movimentacoes.filter(data_movimentacao__date__gte=inicio_janela - timedelta(days=1))
    primeira = movimentos.order_by('data_movimentacao').first()
    if primeira is None:
        return {}
    inicio = max(_dia_local(primeira.data_movimentacao), inicio_janela)
    serie = {inicio + timedelta(days=i): 0.0 for i in range((hoje - inicio).days + 1)}
    for mov in movimentos.filter(CONSUMO):
        dia = _dia_local(mov.data_movimentacao)
        if dia in serie:
            serie[dia] += float(mov.quantidade)
    return serie


def _projetar_prophet(serie):
    # Silencia o log de cada ajuste do Stan e o aviso de plotly ausente (gráficos não são usados)
    logging.getLogger('cmdstanpy').disabled = True
    logging.getLogger('prophet.plot').disabled = True
    import pandas as pd
    from prophet import Prophet

    df = pd.DataFrame({'ds': pd.to_datetime(list(serie)), 'y': list(serie.values())})
    modelo = Prophet(
        growth='linear',
        weekly_seasonality=len(serie) >= MIN_DIAS_PROPHET,
        yearly_seasonality=False,
        daily_seasonality=False,
        uncertainty_samples=0,
    )
    modelo.fit(df)
    futuro = modelo.make_future_dataframe(periods=HORIZONTE_DIAS, include_history=False)
    previsto = modelo.predict(futuro)['yhat'].clip(lower=0)
    return [float(v) for v in previsto]


def _projetar_media_movel(serie):
    ultimos = list(serie.values())[-JANELA_MEDIA_MOVEL:]
    media = sum(ultimos) / len(ultimos) if ultimos else 0.0
    return [media] * HORIZONTE_DIAS


def projetar(serie):
    """Escolhe o modelo pela quantidade de histórico e devolve o consumo diário previsto."""
    dias = len(serie)
    dias_com_consumo = sum(1 for v in serie.values() if v > 0)
    if dias_com_consumo == 0:
        return Projecao(PrevisaoEstoque.Modelo.SEM_CONSUMO, [0.0] * HORIZONTE_DIAS, dias,
                        'Nenhuma saída registrada: não há consumo para projetar.')

    if dias >= MIN_DIAS_PROPHET and dias_com_consumo >= MIN_CONSUMOS_PROPHET:
        try:
            return Projecao(PrevisaoEstoque.Modelo.PROPHET, _projetar_prophet(serie), dias)
        except Exception as erro:  # Prophet não instalado ou ajuste que não converge
            logger.warning('Prophet indisponível, usando média móvel: %s', erro)
            observacao = 'Prophet indisponível no servidor; estimado pela média móvel.'
    else:
        observacao = (f'Histórico curto ({dias} dias, {dias_com_consumo} com consumo); '
                      f'estimado pela média móvel até haver {MIN_DIAS_PROPHET} dias.')
    return Projecao(PrevisaoEstoque.Modelo.MEDIA_MOVEL, _projetar_media_movel(serie), dias, observacao)


def dias_ate_consumir(consumo_diario, quantidade):
    """Quantos dias até o consumo acumulado alcançar a quantidade (None se não alcança no horizonte)."""
    if quantidade <= 0:
        return 0
    acumulado = 0.0
    for dia, consumo in enumerate(consumo_diario, start=1):
        acumulado += consumo
        if acumulado >= quantidade - 1e-9:
            return dia
    return None


def percentual_restante(insumo, hoje=None):
    """Saldo atual em relação ao maior saldo dos últimos JANELA_PERCENTUAL dias (o da última compra)."""
    hoje = hoje or timezone.localdate()
    saldo = float(insumo.quantidade_atual)
    maior = saldo
    limite = hoje - timedelta(days=JANELA_PERCENTUAL)
    # Volta no tempo desfazendo cada movimentação para reconstruir o saldo depois dela
    for mov in insumo.movimentacoes.order_by('-data_movimentacao', '-id'):
        if _dia_local(mov.data_movimentacao) < limite:
            break
        tipo = (mov.tipo_movimentacao or '').strip().upper()
        efeito = mov.quantidade if tipo in ENTRADAS else -mov.quantidade
        saldo -= efeito
        maior = max(maior, saldo)
    if maior <= 0:
        return 0.0
    return round(max(float(insumo.quantidade_atual), 0.0) / maior * 100, 1)


def _ultima_movimentacao_id(insumo):
    return insumo.movimentacoes.aggregate(ultima=Max('id'))['ultima']


def calcular(insumo, hoje=None):
    """Recalcula e grava a previsão do insumo."""
    hoje = hoje or timezone.localdate()
    projecao = projetar(serie_consumo(insumo, hoje))
    saldo = max(float(insumo.quantidade_atual), 0.0)
    minimo = float(insumo.estoque_minimo or 0)

    dias = dias_ate_consumir(projecao.consumo_diario, saldo)
    dias_minimo = dias_ate_consumir(projecao.consumo_diario, saldo - minimo) if minimo > 0 else None
    proximos_30 = projecao.consumo_diario[:30]
    observacao = projecao.observacao
    if dias is None and projecao.modelo != PrevisaoEstoque.Modelo.SEM_CONSUMO:
        observacao = observacao or f'O consumo previsto não esgota o saldo nos próximos {HORIZONTE_DIAS} dias.'

    previsao, _ = PrevisaoEstoque.objects.update_or_create(insumo=insumo, defaults={
        'modelo': projecao.modelo,
        'saldo_considerado': float(insumo.quantidade_atual),
        'consumo_medio_diario': round(sum(proximos_30) / len(proximos_30), 4) if proximos_30 else 0.0,
        'dias_restantes': dias,
        'data_esgotamento': hoje + timedelta(days=dias) if dias is not None else None,
        'dias_ate_minimo': dias_minimo,
        'data_estoque_minimo': hoje + timedelta(days=dias_minimo) if dias_minimo is not None else None,
        'percentual_restante': percentual_restante(insumo, hoje),
        'dias_historico': projecao.dias_historico,
        'observacao': observacao[:255],
        'ultima_movimentacao_id': _ultima_movimentacao_id(insumo),
    })
    return previsao


def desatualizada(previsao, insumo, hoje=None):
    hoje = hoje or timezone.localdate()
    return (
        previsao is None
        or _dia_local(previsao.gerada_em) != hoje
        or previsao.saldo_considerado != float(insumo.quantidade_atual)
        or previsao.ultima_movimentacao_id != _ultima_movimentacao_id(insumo)
    )


def previsoes(recalcular=False, hoje=None):
    """Previsão de todos os insumos, recalculando só as desatualizadas. Mais críticos primeiro."""
    hoje = hoje or timezone.localdate()
    resultado = []
    for insumo in Insumo.objects.select_related('previsao').order_by('nome'):
        previsao = getattr(insumo, 'previsao', None)
        if recalcular or desatualizada(previsao, insumo, hoje):
            previsao = calcular(insumo, hoje)
        resultado.append(previsao)
    resultado.sort(key=lambda p: (p.dias_restantes is None, p.dias_restantes or 0, p.insumo.nome))
    return resultado
