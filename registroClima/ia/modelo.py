"""
Árvore de decisão da irrigação (RF10): treino, persistência com joblib e previsão explicada.

A justificativa é o próprio caminho que a leitura percorreu na árvore, traduzido em
condições legíveis ("umidade do solo abaixo de 39,8 %"), e a confiança vem do predict_proba.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import sklearn
from django.utils import timezone
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

from .dados import FEATURES, ROTULOS, gerar_dataset

logger = logging.getLogger(__name__)

CAMINHO_MODELO = Path(__file__).resolve().parent / 'modelo_irrigacao.joblib'

PARAMETROS_PADRAO = {'amostras': 6000, 'seed': 2026, 'profundidade': 6, 'min_folha': 20}

NOMES = {
    'umidade_solo': ('umidade do solo', '%'),
    'temperatura': ('temperatura', '°C'),
    'umidade_ar': ('umidade do ar', '%'),
    'chuva_prevista_mm': ('chuva prevista nas próximas 6 h', 'mm'),
}


@dataclass
class Decisao:
    irrigar: bool
    confianca: float
    justificativa: str
    condicoes: list = field(default_factory=list)

    @property
    def acao(self):
        return ROTULOS[int(self.irrigar)]


def treinar(amostras=None, seed=None, profundidade=None, min_folha=None):
    """Treina a árvore no dataset sintético. Devolve o pacote pronto para salvar (modelo + metadados)."""
    p = dict(PARAMETROS_PADRAO)
    p.update({k: v for k, v in
              {'amostras': amostras, 'seed': seed, 'profundidade': profundidade, 'min_folha': min_folha}.items()
              if v is not None})

    X, y = gerar_dataset(p['amostras'], p['seed'])
    X_treino, X_teste, y_treino, y_teste = train_test_split(
        X, y, test_size=0.25, random_state=p['seed'], stratify=y,
    )
    # Profundidade limitada e folhas mínimas: árvore curta o bastante para a justificativa ser legível
    # e folhas com amostras suficientes para a confiança não ser sempre 100 %
    modelo = DecisionTreeClassifier(
        max_depth=p['profundidade'], min_samples_leaf=p['min_folha'], random_state=p['seed'],
    )
    modelo.fit(X_treino, y_treino)

    return {
        'modelo': modelo,
        'features': list(FEATURES),
        'sklearn': sklearn.__version__,
        'treinado_em': timezone.now().isoformat(),
        'parametros': p,
        'metricas': {
            'acuracia_teste': round(float(accuracy_score(y_teste, modelo.predict(X_teste))), 4),
            'amostras_treino': int(len(y_treino)),
            'amostras_teste': int(len(y_teste)),
            'folhas': int(modelo.get_n_leaves()),
            'profundidade': int(modelo.get_depth()),
            'importancia': {
                nome: round(float(valor), 4) for nome, valor in zip(FEATURES, modelo.feature_importances_)
            },
        },
    }


def salvar(pacote, caminho=CAMINHO_MODELO):
    joblib.dump(pacote, caminho, compress=3)
    _cache.clear()


_cache = {}


def carregar_modelo(caminho=CAMINHO_MODELO):
    """
    Pacote do modelo versionado no repositório. Se o arquivo faltar ou tiver sido treinado em outra
    versão do scikit-learn, treina de novo em memória (leva menos de um segundo e é determinístico).
    """
    if 'pacote' in _cache:
        return _cache['pacote']

    pacote = None
    try:
        pacote = joblib.load(caminho)
        if pacote.get('sklearn') != sklearn.__version__ or pacote.get('features') != FEATURES:
            logger.warning(
                'Modelo de irrigação treinado com scikit-learn %s (atual %s) ou com outras colunas; '
                'retreinando em memória. Rode "python manage.py treinar_irrigacao" para atualizar o arquivo.',
                pacote.get('sklearn'), sklearn.__version__,
            )
            pacote = None
    except FileNotFoundError:
        logger.warning('Arquivo %s não encontrado; treinando o modelo de irrigação em memória.', caminho)
    except Exception:  # arquivo corrompido ou incompatível
        logger.exception('Falha ao carregar %s; treinando o modelo de irrigação em memória.', caminho)

    if pacote is None:
        pacote = treinar()
    _cache['pacote'] = pacote
    return pacote


def _fmt(valor):
    return f'{valor:.1f}'.replace('.', ',')


def _classes_das_folhas(arvore, no, memo):
    """Conjunto de classes que as folhas abaixo de `no` podem devolver."""
    if no not in memo:
        esquerda, direita = arvore.children_left[no], arvore.children_right[no]
        if esquerda == direita:
            memo[no] = {int(np.argmax(arvore.value[no][0]))}
        else:
            memo[no] = _classes_das_folhas(arvore, esquerda, memo) | _classes_das_folhas(arvore, direita, memo)
    return memo[no]


def _condicoes_do_caminho(modelo, x):
    """
    Junta as divisões do caminho por variável e devolve só os limites mais apertados de cada uma.
    Divisões em que os dois lados levam à mesma decisão ficam de fora: não explicam nada.
    """
    arvore = modelo.tree_
    nos = modelo.decision_path(x.reshape(1, -1)).indices
    memo = {}
    limites = {}  # nome -> [mínimo, máximo]
    for no in nos:
        if arvore.children_left[no] == arvore.children_right[no]:
            continue  # folha
        if len(_classes_das_folhas(arvore, no, memo)) == 1:
            break  # daqui para baixo todas as folhas dão a mesma decisão
        nome = FEATURES[arvore.feature[no]]
        corte = float(arvore.threshold[no])
        minimo, maximo = limites.setdefault(nome, [None, None])
        if x[arvore.feature[no]] <= corte:
            limites[nome][1] = corte if maximo is None else min(maximo, corte)
        else:
            limites[nome][0] = corte if minimo is None else max(minimo, corte)

    condicoes = []
    for nome in FEATURES:  # ordem fixa: solo primeiro, válvula por último
        if nome not in limites:
            continue
        minimo, maximo = limites[nome]
        lido = float(x[FEATURES.index(nome)])
        if nome == 'valvula_aberta':
            condicoes.append('válvula já estava aberta' if lido >= 0.5 else 'válvula estava fechada')
            continue
        rotulo, unidade = NOMES[nome]
        if minimo is not None and maximo is not None:
            faixa = f'entre {_fmt(minimo)} e {_fmt(maximo)} {unidade}'
        elif maximo is not None:
            faixa = f'até {_fmt(maximo)} {unidade}'
        else:
            faixa = f'acima de {_fmt(minimo)} {unidade}'
        verbo = 'previsto' if nome == 'chuva_prevista_mm' else 'lido'
        condicoes.append(f'{rotulo} {faixa} ({verbo} {_fmt(lido)} {unidade})')
    return condicoes


def prever(umidade_solo, temperatura, umidade_ar, chuva_prevista_mm=0.0, valvula_aberta=False, pacote=None):
    """Decide se a mesa deve ser irrigada e explica o porquê pelo caminho percorrido na árvore."""
    pacote = pacote or carregar_modelo()
    modelo = pacote['modelo']
    x = np.array([
        float(umidade_solo), float(temperatura), float(umidade_ar),
        float(chuva_prevista_mm or 0.0), 1.0 if valvula_aberta else 0.0,
    ])
    probabilidades = modelo.predict_proba(x.reshape(1, -1))[0]
    classe = int(modelo.classes_[int(np.argmax(probabilidades))])
    condicoes = _condicoes_do_caminho(modelo, x)
    conclusao = 'irrigar' if classe == 1 else 'não irrigar'
    return Decisao(
        irrigar=bool(classe),
        confianca=round(float(np.max(probabilidades)), 4),
        justificativa=f'{conclusao.capitalize()}: ' + '; '.join(condicoes) + '.',
        condicoes=condicoes,
    )
