from django.core.management.base import BaseCommand
from sklearn.tree import export_text

from registroClima.ia.dados import FEATURES
from registroClima.ia.modelo import CAMINHO_MODELO, PARAMETROS_PADRAO, salvar, treinar


class Command(BaseCommand):
    help = (
        'Treina a árvore de decisão da irrigação (RF10) no dataset sintético de regras agronômicas '
        'e salva em registroClima/ia/modelo_irrigacao.joblib.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--amostras', type=int, default=PARAMETROS_PADRAO['amostras'])
        parser.add_argument('--seed', type=int, default=PARAMETROS_PADRAO['seed'])
        parser.add_argument('--profundidade', type=int, default=PARAMETROS_PADRAO['profundidade'])
        parser.add_argument('--min-folha', type=int, default=PARAMETROS_PADRAO['min_folha'])
        parser.add_argument('--mostrar-arvore', action='store_true', help='Imprime as regras da árvore.')
        parser.add_argument('--dry-run', action='store_true', help='Treina e mostra as métricas sem salvar.')

    def handle(self, *args, **opts):
        pacote = treinar(opts['amostras'], opts['seed'], opts['profundidade'], opts['min_folha'])
        m = pacote['metricas']

        self.stdout.write(
            f'Acurácia no teste: {m["acuracia_teste"]:.1%} '
            f'({m["amostras_treino"]} amostras de treino, {m["amostras_teste"]} de teste)'
        )
        self.stdout.write(f'Árvore: profundidade {m["profundidade"]}, {m["folhas"]} folhas')
        self.stdout.write('Importância das variáveis:')
        for nome, valor in sorted(m['importancia'].items(), key=lambda item: -item[1]):
            self.stdout.write(f'  {nome:<18} {valor:.1%}')

        if opts['mostrar_arvore']:
            self.stdout.write(export_text(pacote['modelo'], feature_names=FEATURES, decimals=1))

        if opts['dry_run']:
            self.stdout.write(self.style.WARNING('Dry run: modelo não salvo.'))
            return
        salvar(pacote)
        self.stdout.write(self.style.SUCCESS(f'Modelo salvo em {CAMINHO_MODELO}'))
