"""
Liga a árvore de decisão (modelo.py) aos dados do sistema: última leitura da mesa, estado da
válvula e previsão de chuva da cidade. No modo automático a decisão vira um RegistroIrrigacao,
que faz o papel do comando ao relé enquanto não há hardware.
"""
from django.db import transaction

from configuracao.previsao import previsao_chuva
from mesa.models import Mesa
from registroClima.models import DecisaoIrrigacao, ModoIrrigacao, RegistroClima, RegistroIrrigacao
from registroClima.simulacao import PREFIXO_SIMULADO

from .modelo import carregar_modelo, prever

PREFIXO_IA = '[IA]'
FLUXO_PADRAO_L_MIN = 8.0


def valvula_da_mesa(mesa):
    """(id da válvula, último registro). Sem registro ainda, a válvula é VLV-<id da mesa>."""
    ultimo = RegistroIrrigacao.objects.filter(mesa_id=mesa).order_by('-data_registro', '-id').first()
    return (ultimo.valvula_id if ultimo else f'VLV-{mesa.id:02d}'), ultimo


def ultima_leitura_com_solo(mesa):
    return (
        RegistroClima.objects.filter(mesa_id=mesa, umidade_solo__isnull=False)
        .order_by('-data_registro', '-id').first()
    )


def acao_para(irrigar, aberta):
    A = DecisaoIrrigacao.Acao
    if irrigar:
        return A.MANTER_ABERTA if aberta else A.ABRIR
    return A.FECHAR if aberta else A.MANTER_FECHADA


def muda_a_valvula(decisao):
    return decisao.acao in (DecisaoIrrigacao.Acao.ABRIR, DecisaoIrrigacao.Acao.FECHAR)


def registrar_decisao(mesa, *, umidade_solo, temperatura, umidade_ar, valvula_id, aberta, previsao,
                      modo=None, leitura=None, simulado=False, agora=None, pacote=None):
    """Consulta a árvore com as entradas dadas e grava a DecisaoIrrigacao (ainda sem acionar a válvula)."""
    pacote = pacote or carregar_modelo()
    resultado = prever(
        umidade_solo=umidade_solo, temperatura=temperatura, umidade_ar=umidade_ar,
        chuva_prevista_mm=previsao.chuva_mm, valvula_aberta=aberta, pacote=pacote,
    )
    justificativa = resultado.justificativa
    if not previsao.disponivel and previsao.motivo:
        justificativa = f'{justificativa} {previsao.motivo}'

    return DecisaoIrrigacao.objects.create(
        mesa_id=mesa,
        valvula_id=valvula_id,
        acao=acao_para(resultado.irrigar, aberta),
        irrigar=resultado.irrigar,
        confianca=resultado.confianca,
        justificativa=justificativa,
        leitura=leitura,
        umidade_solo=round(float(umidade_solo), 2),
        temperatura=round(float(temperatura), 2),
        umidade_ar=round(float(umidade_ar), 2),
        chuva_prevista_mm=previsao.chuva_mm,
        previsao_disponivel=previsao.disponivel,
        valvula_estava_aberta=aberta,
        modo=modo or ModoIrrigacao.atual().modo,
        modelo_treinado_em=pacote.get('treinado_em', '')[:40],
        simulado=simulado,
        **({'data_decisao': agora} if agora else {}),
    )


def executar_decisao(decisao, fluxo_l_min=FLUXO_PADRAO_L_MIN, consumo_ciclo_l=0, agora=None):
    """Transforma abrir/fechar em comando na válvula (RegistroIrrigacao). Manter não gera comando."""
    if not muda_a_valvula(decisao):
        return None
    status = 'ativa' if decisao.acao == DecisaoIrrigacao.Acao.ABRIR else 'inativa'
    prefixo = f'{PREFIXO_SIMULADO} {PREFIXO_IA}' if decisao.simulado else PREFIXO_IA
    registro = RegistroIrrigacao.objects.create(
        mesa_id=decisao.mesa_id,
        valvula_id=decisao.valvula_id,
        status_atual=status,
        fluxo_l_min=fluxo_l_min if status == 'ativa' else 0,
        consumo_ciclo_l=consumo_ciclo_l,
        simulado=decisao.simulado,
        observacoes=(f'{prefixo} {decisao.get_acao_display()} ({float(decisao.confianca):.0%}). '
                     f'{decisao.justificativa}'),
        **({'data_registro': agora} if agora else {}),
    )
    decisao.registro_irrigacao = registro
    decisao.executada = True
    decisao.save(update_fields=['registro_irrigacao', 'executada'])
    return registro


@transaction.atomic
def decidir_mesa(mesa, executar=None, previsao=None, agora=None):
    """
    Decide a válvula de uma mesa pela última leitura com umidade do solo. Sem ela não há como
    decidir: devolve None. `executar` padrão segue o modo (só o automático aciona a válvula).
    """
    leitura = ultima_leitura_com_solo(mesa)
    if leitura is None:
        return None

    valvula_id, ultimo_registro = valvula_da_mesa(mesa)
    modo = ModoIrrigacao.atual().modo
    decisao = registrar_decisao(
        mesa,
        umidade_solo=leitura.umidade_solo,
        temperatura=leitura.temperatura,
        umidade_ar=leitura.umidade,
        valvula_id=valvula_id,
        aberta=bool(ultimo_registro and ultimo_registro.status_atual == 'ativa'),
        previsao=previsao or previsao_chuva(),
        modo=modo,
        leitura=leitura,
        simulado=leitura.simulado,
        agora=agora,
    )
    if executar is None:
        executar = modo == ModoIrrigacao.Modo.AUTOMATICO_IA
    if executar:
        executar_decisao(decisao, agora=agora)
    return decisao


def decidir_todas(executar=None):
    """Uma decisão por mesa instalada em estufa. A previsão de chuva é consultada uma vez só."""
    previsao = previsao_chuva()
    decisoes = []
    for mesa in Mesa.objects.filter(estufa__isnull=False).order_by('id'):
        decisao = decidir_mesa(mesa, executar=executar, previsao=previsao)
        if decisao:
            decisoes.append(decisao)
    return decisoes
