"""
Dataset sintético para a árvore de decisão da irrigação (RF10).

Sem histórico real de irrigação, o rótulo vem de regras agronômicas aplicadas aos valores
verdadeiros do ambiente. O modelo, porém, só enxerga o que os sensores leriam: os valores
com ruído de medição. Perto dos limites a árvore fica em dúvida, e é isso que dá sentido
à confiança devolvida pelo predict_proba.
"""
import numpy as np

# Ordem das colunas que o modelo espera
FEATURES = ['umidade_solo', 'temperatura', 'umidade_ar', 'chuva_prevista_mm', 'valvula_aberta']

ROTULOS = {0: 'nao_irrigar', 1: 'irrigar'}

# Limites agronômicos (umidade do solo em %, temperatura em °C, umidade do ar em %, chuva em mm nas próximas 6 h)
SOLO_CRITICO = 30.0          # abaixo disso irriga sempre, mesmo com chuva prevista
SOLO_ABRE = 40.0             # abaixo disso irriga
SOLO_FECHA = 65.0            # válvula aberta irriga até aqui (histerese)
SOLO_EVAPOTRANSPIRACAO = 50.0
TEMP_EVAPOTRANSPIRACAO = 30.0
AR_SECO = 50.0
CHUVA_SUFICIENTE = 5.0

# Desvio padrão do ruído de cada sensor
RUIDO = {'umidade_solo': 1.5, 'temperatura': 0.5, 'umidade_ar': 2.0, 'chuva_prevista_mm': 0.8}


def regra_agronomica(solo, temp, ar, chuva, aberta):
    """Decisão de referência (1 = irrigar) a partir dos valores reais do ambiente."""
    if solo < SOLO_CRITICO:
        return 1
    if chuva >= CHUVA_SUFICIENTE:
        return 0  # a chuva prevista repõe a umidade, economiza água
    if solo < SOLO_ABRE:
        return 1
    if solo >= SOLO_FECHA:
        return 0
    if aberta:
        return 1  # já está irrigando: segue até fechar acima de 65 %
    # Válvula fechada na faixa intermediária: só antecipa com calor e ar seco
    if solo < SOLO_EVAPOTRANSPIRACAO and temp > TEMP_EVAPOTRANSPIRACAO and ar < AR_SECO:
        return 1
    return 0


def gerar_dataset(amostras=6000, seed=2026):
    """Devolve (X, y): X com as colunas de FEATURES como os sensores leriam, y com a decisão de referência."""
    rng = np.random.default_rng(seed)
    solo = rng.uniform(10, 95, amostras)
    temp = rng.uniform(12, 40, amostras)
    ar = rng.uniform(25, 98, amostras)
    # A maior parte das janelas não tem chuva; o resto vai de garoa a temporal
    chuva = np.where(rng.random(amostras) < 0.6, 0.0, rng.gamma(1.5, 4.0, amostras))
    aberta = (rng.random(amostras) < 0.4).astype(int)

    y = np.array([regra_agronomica(*linha) for linha in zip(solo, temp, ar, chuva, aberta)])

    lido = {
        'umidade_solo': np.clip(solo + rng.normal(0, RUIDO['umidade_solo'], amostras), 0, 100),
        'temperatura': temp + rng.normal(0, RUIDO['temperatura'], amostras),
        'umidade_ar': np.clip(ar + rng.normal(0, RUIDO['umidade_ar'], amostras), 0, 100),
        'chuva_prevista_mm': np.clip(chuva + rng.normal(0, RUIDO['chuva_prevista_mm'], amostras), 0, None),
        'valvula_aberta': aberta,
    }
    X = np.column_stack([lido[nome] for nome in FEATURES])
    return X, y
