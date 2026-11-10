from django.core.management.base import BaseCommand, CommandError

from insumo.models import Insumo
from insumo.previsao import calcular, previsoes


class Command(BaseCommand):
    help = 'Recalcula a previsão de fim de estoque dos insumos (Prophet, com média móvel como contingência).'

    def add_arguments(self, parser):
        parser.add_argument('--insumo', type=int, help='Recalcula só o insumo com este id.')

    def handle(self, *args, **opts):
        if opts['insumo']:
            insumo = Insumo.objects.filter(pk=opts['insumo']).first()
            if insumo is None:
                raise CommandError(f'Insumo {opts["insumo"]} não encontrado.')
            resultado = [calcular(insumo)]
        else:
            resultado = previsoes(recalcular=True)

        for p in resultado:
            fim = f'{p.dias_restantes} dias ({p.data_esgotamento:%d/%m/%Y})' if p.dias_restantes is not None \
                else 'sem previsão de esgotamento'
            comprar = f', comprar até {p.data_estoque_minimo:%d/%m/%Y}' if p.data_estoque_minimo else ''
            self.stdout.write(
                f'{p.insumo.nome}: {p.insumo.quantidade_atual:g} {p.insumo.unidade}, '
                f'{p.consumo_medio_diario:.2f} {p.insumo.unidade}/dia -> {fim}{comprar} [{p.get_modelo_display()}]'
            )
        self.stdout.write(self.style.SUCCESS(f'{len(resultado)} previsões atualizadas.'))
