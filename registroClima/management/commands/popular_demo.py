import math
import random
from datetime import datetime, time, timedelta

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from alerta.models import Alerta
from alerta.services import faixa_da_mesa, gerar_alertas
from colheita.models import Colheita
from cultura.models import Cultura
from estoque.models import Estoque
from estufa.models import Estufa
from funcionarios.models import Funcionario
from insumo.models import Insumo, MovimentacaoInsumo
from lotePlantio.models import LotePlantio
from mesa.models import Mesa
from configuracao.models import LocalizacaoPropriedade
from configuracao.previsao import PrevisaoChuva
from registroClima.ia.modelo import carregar_modelo
from registroClima.ia.servico import executar_decisao, registrar_decisao
from registroClima.models import DecisaoIrrigacao, ModoIrrigacao, RegistroClima, RegistroIrrigacao
from registroClima.simulacao import PREFIXO_SIMULADO

AT, ES, BX, CO, PE = (LotePlantio.StatusPlantio.ATIVO, LotePlantio.StatusPlantio.EM_ESTOQUE,
                      LotePlantio.StatusPlantio.ESTOQUE_BAIXO, LotePlantio.StatusPlantio.COLHIDO,
                      LotePlantio.StatusPlantio.PERDIDO)

# nome, dias até a colheita, temp. mínima, temp. máxima, umidade ideal, descrição
CULTURAS = [
    ('Alface Crespa', 45, 15, 24, 70, 'Folhosa de ciclo curto, cultivada em perfis NFT.'),
    ('Rúcula', 35, 15, 25, 70, 'Folhosa de crescimento rápido, sensível a calor excessivo.'),
    ('Manjericão', 50, 18, 30, 60, 'Erva aromática; colheita por desbaste das pontas.'),
    ('Tomate Cereja', 90, 18, 29, 65, 'Fruto em cachos, cultivado em vasos com fibra de coco.'),
    ('Morango', 80, 13, 26, 70, 'Cultivo semi-hidropônico em bancadas suspensas.'),
    ('Pimentão', 100, 18, 30, 65, 'Ciclo longo; exige solo úmido e boa luminosidade.'),
]

# nome, tipo de cultivo, capacidade, mesas (identificação, capacidade, tem sensor de solo e válvula)
ESTUFAS = [
    ('Estufa A - Folhosas', 'Hidroponia NFT', 600, [('A1', 150, False), ('A2', 150, False),
                                                    ('A3', 150, False), ('A4', 150, False)]),
    ('Estufa B - Frutíferas', 'Semi-hidropônico', 400, [('B1', 130, True), ('B2', 130, True),
                                                       ('B3', 130, True)]),
    ('Estufa C - Berçário', 'Mudas em bandejas', 200, [('C1', 90, True), ('C2', 90, True)]),
]

# mesa, cultura, dias desde o plantio, status, quantidade, unidade
LOTES_EM_CULTIVO = [
    ('A1', 'Alface Crespa', 46, AT, 140, 'UN'),
    ('A2', 'Rúcula', 21, AT, 130, 'UN'),
    ('A3', 'Alface Crespa', 25, AT, 145, 'UN'),
    ('B1', 'Tomate Cereja', 67, AT, 120, 'UN'),
    ('B2', 'Morango', 72, AT, 125, 'UN'),
    ('B3', 'Pimentão', 44, AT, 110, 'UN'),
    ('C1', 'Manjericão', 28, AT, 85, 'UN'),
    ('C2', 'Alface Crespa', 8, ES, 6, 'BD'),
    ('C2', 'Rúcula', 5, BX, 1, 'BD'),
]

# mesa, cultura, dias desde o plantio, dias desde a colheita, plantado, colhido, perdido
LOTES_COLHIDOS = [
    ('A1', 'Alface Crespa', 98, 52, 140, 132, 8),
    ('A2', 'Rúcula', 62, 26, 130, 118, 12),
    ('C1', 'Manjericão', 82, 31, 85, 80, 5),
    ('A4', 'Alface Crespa', 51, 6, 150, 141, 9),
]

# mesa, cultura, dias desde o plantio, dias desde a perda, quantidade, motivo
LOTES_PERDIDOS = [
    ('A3', 'Rúcula', 56, 40, 130, 'Infestação de pulgão detectada tarde; lote descartado.'),
]

# nome, tipo, unidade, estoque mínimo, fornecedor, dias até vencer, compras (dias atrás, quantidade),
# consumo por dia útil no início do histórico, fator do consumo no fim (1,6 = consumo 60% maior hoje)
INSUMOS = [
    ('Nitrato de Cálcio', 'FE', 'kg', 10, 'AgroNutri Distribuidora', 540,
     [(90, 25), (60, 25), (30, 25), (12, 15)], 1.0, 1.6),
    ('Nitrato de Potássio', 'FE', 'kg', 8, 'AgroNutri Distribuidora', 600, [(90, 25), (45, 20)], 0.45, 1.2),
    ('Sulfato de Magnésio', 'FE', 'kg', 5, 'AgroNutri Distribuidora', 720, [(90, 20), (40, 10)], 0.3, 1.0),
    ('MAP Purificado', 'FE', 'kg', 5, 'Campo Forte Insumos', 480, [(90, 20)], 0.25, 1.0),
    ('Óleo de Neem', 'DF', 'L', 2, 'BioDefesa Agrícola', 200, [(90, 5), (30, 3)], 0.06, 1.3),
    ('Bacillus thuringiensis', 'DF', 'L', 1, 'BioDefesa Agrícola', 12, [(90, 3)], 0.04, 1.0),
    ('Fibra de Coco', 'SB', 'saco', 10, 'Campo Forte Insumos', None, [(90, 40), (20, 10)], 0.5, 1.0),
    ('Espuma Fenólica', 'SB', 'placa', 20, 'Hidro Mudas Ltda', None, [(90, 60), (50, 30), (15, 20)], 1.2, 1.4),
    ('Ácido Fosfórico (correção de pH)', 'OU', 'L', 2, 'AgroNutri Distribuidora', 365, [(90, 5), (45, 5)],
     0.08, 1.0),
]
HISTORICO_INSUMOS_DIAS = 90

# nome, CPF, telefone, usuário, grupo
EQUIPE = [
    ('Carla Mendes', '321.654.987-00', '(19) 99812-4410', 'carla.mendes', 'gerente'),
    ('Rafael Souza', '456.789.123-11', '(19) 99745-2290', 'rafael.souza', 'operador'),
    ('Bruna Lima', '789.123.456-22', '(19) 99630-7815', 'bruna.lima', 'tecnico'),
    ('Diego Martins', '159.753.486-33', '(19) 99521-3364', None, None),
]


class Command(BaseCommand):
    help = (
        'Popula o banco com dados coerentes de demonstração: estufas, mesas, culturas, lotes, colheitas, '
        'estoque, insumos, equipe e um histórico simulado de clima, irrigação e alertas.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--limpar', action='store_true',
                            help='Apaga os dados de domínio antes de popular (usuários são mantidos).')
        parser.add_argument('--dias', type=int, default=7, help='Dias de histórico de clima e irrigação.')
        parser.add_argument('--senha', default='GreenTech@2026', help='Senha dos usuários de demonstração.')
        parser.add_argument('--seed', type=int, default=2026, help='Semente para gerar sempre os mesmos dados.')

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts['limpar']:
            self._limpar()
        elif Estufa.objects.exists():
            raise CommandError('O banco já tem estufas cadastradas. Rode com --limpar para recriar a demonstração.')

        self.rng = random.Random(opts['seed'])
        self.hoje = timezone.localdate()
        self.agora = timezone.now().replace(second=0, microsecond=0) - timedelta(minutes=5)

        self.equipe = self._criar_equipe(opts['senha'])
        self.culturas = self._criar_culturas()
        self.mesas = self._criar_estrutura()
        self._criar_lotes()
        self._criar_insumos()
        leituras, irrigacoes, decisoes = self._criar_historico_clima(opts['dias'])
        # A demonstração mostra a IA no comando das válvulas, ligada pela gerente
        ModoIrrigacao.objects.update_or_create(pk=1, defaults={
            'modo': ModoIrrigacao.Modo.AUTOMATICO_IA, 'atualizado_por': User.objects.get(username='carla.mendes'),
        })

        ativos = Alerta.objects.filter(status=Alerta.Status.ATIVO).count()
        self.stdout.write(self.style.SUCCESS(
            f'Demonstração criada: {Estufa.objects.count()} estufas, {Mesa.objects.count()} mesas, '
            f'{LotePlantio.objects.count()} lotes, {Colheita.objects.count()} colheitas, '
            f'{Insumo.objects.count()} insumos, {leituras} leituras, {irrigacoes} registros de irrigação, '
            f'{decisoes} decisões da IA, '
            f'{Alerta.objects.count()} alertas ({ativos} ativos).'
        ))
        self.stdout.write(f'Usuários de demonstração (senha "{opts["senha"]}"): '
                          + ', '.join(u for _, _, _, u, _ in EQUIPE if u))

    def _limpar(self):
        for modelo in (Alerta, DecisaoIrrigacao, RegistroIrrigacao, RegistroClima, Colheita, Estoque, MovimentacaoInsumo,
                       Insumo, LotePlantio, Mesa, Estufa, Cultura):
            modelo.objects.all().delete()
        # Funcionários ligados a um login (como o do admin) continuam existindo
        Funcionario.objects.filter(usuario__isnull=True).delete()

    def _dia(self, dias_atras):
        return self.hoje - timedelta(days=dias_atras)

    def _momento(self, dias_atras, hora):
        """Data e hora local de N dias atrás, sem passar do momento atual."""
        momento = timezone.make_aware(datetime.combine(self._dia(dias_atras), time(hora)))
        return min(momento, self.agora)

    def _criar_equipe(self, senha):
        equipe = {}
        for nome, cpf, telefone, username, grupo in EQUIPE:
            usuario = None
            if username:
                usuario, criado = User.objects.get_or_create(
                    username=username, defaults={'first_name': nome.split()[0], 'last_name': nome.split()[-1]},
                )
                if criado:
                    usuario.set_password(senha)
                    usuario.save()
                usuario.groups.add(Group.objects.get_or_create(name=grupo)[0])
            funcionario, _ = Funcionario.objects.update_or_create(
                cpf=cpf, defaults={'nome_completo': nome, 'telefone': telefone, 'usuario': usuario},
            )
            equipe[username or nome] = funcionario
        return equipe

    def _funcionario(self, username='rafael.souza'):
        return self.equipe[username]

    def _criar_culturas(self):
        return {
            nome: Cultura.objects.create(
                nome_cultura=nome, tempo_medio_colheita=ciclo, temperatura_minima=t_min,
                temperatura_maxima=t_max, umidade_ideal=umidade, descricao=descricao,
            )
            for nome, ciclo, t_min, t_max, umidade, descricao in CULTURAS
        }

    def _criar_estrutura(self):
        mesas = {}
        for nome, tipo, capacidade, mesas_da_estufa in ESTUFAS:
            estufa = Estufa.objects.create(nome_setor=nome, tipo_cultivo=tipo, capacidade_maxima=capacidade)
            for identificacao, capacidade_mesa, tem_solo in mesas_da_estufa:
                mesa = Mesa.objects.create(estufa=estufa, identificacao=identificacao,
                                           capacidade_maxima=capacidade_mesa)
                mesa.tem_solo = tem_solo
                mesas[identificacao] = mesa
        a4 = mesas['A4']
        a4.observacoes = 'Perfis higienizados após a colheita de 20/10.'
        a4.save()
        return mesas

    def _entrada_estoque(self, lote, quando, motivo):
        mov = Estoque.objects.create(
            lote_id=lote, funcionario_id=self._funcionario(), tipo_movimentacao='Entrada',
            quantidade=lote.quantidade, unidade=lote.unidade, motivo=motivo,
            observacoes=f'Fornecedor: {lote.fornecedor}' if lote.fornecedor else None,
        )
        # data_movimentacao é auto_now_add: ajusta depois para a data real do plantio
        Estoque.objects.filter(pk=mov.pk).update(data_movimentacao=quando)

    def _criar_lotes(self):
        for mesa, cultura, dias, status, quantidade, unidade in LOTES_EM_CULTIVO:
            muda = status in (ES, BX)
            lote = LotePlantio.objects.create(
                cultura_id=self.culturas[cultura], mesa_id=self.mesas[mesa], data_plantio=self._dia(dias),
                status=status, quantidade=quantidade, unidade=unidade,
                fornecedor='Hidro Mudas Ltda' if muda else None,
                validade=self._dia(-10) if muda else None,
            )
            motivo = 'Bandejas de mudas recebidas' if muda else 'Entrada Inicial de Lote'
            self._entrada_estoque(lote, self._momento(dias, 8), motivo)

        colhedores = ['rafael.souza', 'Diego Martins', 'rafael.souza', 'Diego Martins']
        for (mesa, cultura, dias, dias_colheita, plantado, colhido, perdido), quem in zip(LOTES_COLHIDOS, colhedores):
            lote = LotePlantio.objects.create(
                cultura_id=self.culturas[cultura], mesa_id=self.mesas[mesa], data_plantio=self._dia(dias),
                status=AT, quantidade=plantado, unidade='UN',
            )
            self._entrada_estoque(lote, self._momento(dias, 8), 'Entrada Inicial de Lote')
            colheita = Colheita.objects.create(lote_id=lote, funcionario_id=self._funcionario(quem),
                                               quantidade_colhida=colhido, quantidade_perda=perdido)
            Colheita.objects.filter(pk=colheita.pk).update(data_colheita=self._dia(dias_colheita))
            for tipo, quantidade, motivo in (('Saída', colhido, 'Baixa por Colheita'),
                                             ('Perda', perdido, 'Descarte na Colheita')):
                mov = Estoque.objects.create(lote_id=lote, funcionario_id=self._funcionario(quem),
                                             tipo_movimentacao=tipo, quantidade=quantidade, unidade='UN',
                                             motivo=motivo)
                Estoque.objects.filter(pk=mov.pk).update(data_movimentacao=self._momento(dias_colheita, 9))
            lote.status, lote.quantidade = CO, 0
            lote.save()

        for mesa, cultura, dias, dias_perda, quantidade, motivo in LOTES_PERDIDOS:
            lote = LotePlantio.objects.create(
                cultura_id=self.culturas[cultura], mesa_id=self.mesas[mesa], data_plantio=self._dia(dias),
                status=PE, quantidade=0, unidade='UN',
            )
            lote.quantidade = quantidade
            self._entrada_estoque(lote, self._momento(dias, 8), 'Entrada Inicial de Lote')
            mov = Estoque.objects.create(lote_id=lote, funcionario_id=self._funcionario('bruna.lima'),
                                         tipo_movimentacao='Perda', quantidade=quantidade, unidade='UN',
                                         motivo=motivo)
            Estoque.objects.filter(pk=mov.pk).update(data_movimentacao=self._momento(dias_perda, 10))

    def _movimentar_insumo(self, insumo, tipo, quantidade, quando, motivo, quem='rafael.souza'):
        mov = MovimentacaoInsumo.objects.create(insumo_id=insumo, funcionario_id=self._funcionario(quem),
                                                tipo_movimentacao=tipo, quantidade=quantidade, motivo=motivo)
        MovimentacaoInsumo.objects.filter(pk=mov.pk).update(data_movimentacao=quando)

    def _criar_insumos(self):
        """90 dias de compras e de consumo em dias úteis, base da previsão de fim de estoque (RF09)."""
        for nome, tipo, unidade, minimo, fornecedor, vence_em, compras, base, fator in INSUMOS:
            insumo = Insumo.objects.create(
                nome=nome, tipo=tipo, unidade=unidade, estoque_minimo=minimo, fornecedor=fornecedor,
                validade=self._dia(-vence_em) if vence_em else None,
            )
            compras = dict(compras)
            saldo = 0.0
            for dias_atras in range(HISTORICO_INSUMOS_DIAS, 0, -1):
                if dias_atras in compras:
                    saldo += compras[dias_atras]
                    self._movimentar_insumo(insumo, 'Entrada', compras[dias_atras], self._momento(dias_atras, 7),
                                            'Compra (nota fiscal)', quem='carla.mendes')
                if self._dia(dias_atras).weekday() >= 5:
                    continue  # sem preparo de solução no fim de semana
                # Consumo cresce em linha reta do início ao fim do histórico, com variação do dia a dia
                progresso = 1 - dias_atras / HISTORICO_INSUMOS_DIAS
                usado = round(min(base * (1 + (fator - 1) * progresso) * self.rng.uniform(0.75, 1.25), saldo), 2)
                if usado <= 0:
                    continue
                saldo -= usado
                self._movimentar_insumo(insumo, 'Saída', usado, self._momento(dias_atras, 9),
                                        'Preparo da solução nutritiva' if tipo == 'FE' else 'Uso nas mesas')
            if nome == 'Óleo de Neem' and saldo > 0.5:
                saldo -= 0.5
                self._movimentar_insumo(insumo, 'Perda', 0.5, self._momento(18, 15),
                                        'Frasco danificado no transporte', quem='bruna.lima')
            insumo.quantidade_atual = round(saldo, 2)
            insumo.save()

    def _eventos(self):
        """Anomalias planejadas: (mesas, início, fim, efeito). As do fim do período ficam com alerta ativo."""
        return [
            (('A1', 'A3'), self._momento(4, 12), self._momento(4, 16), 'calor'),
            (('B1', 'B2', 'B3'), self._momento(2, 3), self._momento(2, 6), 'frio'),
            (('C1',), self._momento(1, 13), self._momento(1, 15), 'ar_seco'),
            (('A2',), self.agora - timedelta(hours=2), self.agora, 'calor_leve'),
            (('C1',), self.agora - timedelta(hours=3), self.agora, 'ar_seco_forte'),
        ]

    def _previsao(self, momento, cidade):
        """Previsão de chuva das 6 h seguintes: seca no período, com uma frente de chuva ontem."""
        if self._momento(1, 6) <= momento <= self._momento(1, 18):
            return PrevisaoChuva(9.5, 85, 6, True, cidade)
        return PrevisaoChuva(0.0, self.rng.randint(0, 15), 6, True, cidade)

    def _criar_historico_clima(self, dias):
        eventos = self._eventos()
        resolvedores = [User.objects.get(username=u) for u in ('rafael.souza', 'bruna.lima', 'carla.mendes')]
        momentos = [self.agora - timedelta(hours=h) for h in range(dias * 24, -1, -1)]
        total_leituras = total_irrigacoes = total_decisoes = 0
        pacote = carregar_modelo()
        localizacao = LocalizacaoPropriedade.atual()
        cidade = str(localizacao) if localizacao else None
        automatico = ModoIrrigacao.Modo.AUTOMATICO_IA

        for identificacao, mesa in self.mesas.items():
            if not mesa.lote_em_cultivo() and identificacao != 'C2':
                continue
            faixa, _ = faixa_da_mesa(mesa)
            centro = (faixa['temp_min'] + faixa['temp_max']) / 2
            amplitude = (faixa['temp_max'] - faixa['temp_min']) / 2 * 0.5
            solo = self.rng.uniform(50, 68) if mesa.tem_solo else None
            secagem = self.rng.uniform(0.3, 0.4)
            valvula, estado = f'VLV-{identificacao}', 'inativa'
            ph = self.rng.uniform(5.9, 6.3)

            for momento in momentos:
                local = timezone.localtime(momento)
                hora = local.hour + local.minute / 60
                ciclo_dia = math.sin(2 * math.pi * (hora - 9) / 24)  # pico às 15h, mínimo às 3h
                efeito = next((e for m, ini, fim, e in eventos if identificacao in m and ini <= momento <= fim), None)

                temperatura = min(max(centro + amplitude * ciclo_dia + self.rng.gauss(0, 0.4),
                                      faixa['temp_min'] + 0.3), faixa['temp_max'] - 0.3)
                umidade = min(max(faixa['umidade_ideal'] - 6 * ciclo_dia + self.rng.gauss(0, 2),
                                  faixa['umidade_ideal'] - 12), faixa['umidade_ideal'] + 12)
                if efeito == 'calor':
                    temperatura, umidade = faixa['temp_max'] + self.rng.uniform(4.5, 6.5), umidade - 6
                elif efeito == 'calor_leve':
                    temperatura = faixa['temp_max'] + self.rng.uniform(1, 2)
                elif efeito == 'frio':
                    temperatura = faixa['temp_min'] - self.rng.uniform(2, 3.5)
                elif efeito == 'ar_seco':
                    umidade = faixa['umidade_ideal'] - self.rng.uniform(17, 22)
                elif efeito == 'ar_seco_forte':
                    umidade = faixa['umidade_ideal'] - self.rng.uniform(26, 30)

                sol = max(0.0, math.sin(math.pi * (hora - 6) / 12))
                if solo is not None:
                    solo = max(solo - secagem * (1.4 if sol else 0.6), 20)
                    if identificacao == 'B2' and momento == self.agora:
                        solo = 36.4  # termina com o solo seco e a válvula recém-aberta

                leitura = RegistroClima.objects.create(
                    mesa_id=mesa, data_registro=momento,
                    temperatura=round(temperatura, 2), umidade=round(umidade, 2),
                    luminosidade=round(sol * self.rng.uniform(32000, 48000) + self.rng.uniform(0, 40), 2),
                    ventilacao=90 if efeito in ('calor', 'calor_leve') else int(25 + 35 * (ciclo_dia + 1) / 2),
                    umidade_solo=round(solo, 2) if solo is not None else None,
                    co2=round((self.rng.uniform(420, 520) if sol else self.rng.uniform(650, 820)), 2),
                    ph=round(ph + self.rng.gauss(0, 0.05), 2),
                    simulado=True,
                    observacoes=f'{PREFIXO_SIMULADO} Histórico gerado para demonstração'
                                + (f' (evento: {efeito})' if efeito else ''),
                )
                total_leituras += 1
                abertos = {a.parametro for a in gerar_alertas(leitura)}

                # Problema que sumiu na leitura nova: a equipe marca o alerta como resolvido
                for alerta in Alerta.objects.filter(mesa_id=mesa, status=Alerta.Status.ATIVO).exclude(
                        parametro__in=abertos):
                    alerta.status = Alerta.Status.RESOLVIDO
                    alerta.resolvido_em = min(momento + timedelta(minutes=self.rng.randint(5, 40)), self.agora)
                    alerta.resolvido_por = self.rng.choice(resolvedores)
                    alerta.save()

                if solo is None:
                    continue
                # A árvore de decisão (RF10) comanda a válvula a cada leitura
                previsao = self._previsao(momento, cidade)
                decisao = registrar_decisao(
                    mesa, umidade_solo=solo, temperatura=temperatura, umidade_ar=umidade, valvula_id=valvula,
                    aberta=estado == 'ativa', previsao=previsao, modo=automatico, leitura=leitura,
                    simulado=True, agora=momento, pacote=pacote,
                )
                total_decisoes += 1
                if decisao.acao == DecisaoIrrigacao.Acao.ABRIR:
                    fluxo = round(self.rng.uniform(6, 10), 2)
                    duracao = self.rng.randint(15, 22)
                    executar_decisao(decisao, fluxo, 0, agora=momento + timedelta(minutes=1))
                    estado = 'ativa'
                    total_irrigacoes += 1
                    if momento == self.agora:
                        continue  # irrigação em andamento
                    # Ao fim do ciclo o solo está úmido e a IA manda fechar
                    solo = max(solo + duracao * self.rng.uniform(1.6, 1.9), 65.5 + self.rng.uniform(0, 4))
                    fim = momento + timedelta(minutes=1 + duracao)
                    fechamento = registrar_decisao(
                        mesa, umidade_solo=solo, temperatura=temperatura, umidade_ar=umidade, valvula_id=valvula,
                        aberta=True, previsao=previsao, modo=automatico, simulado=True, agora=fim, pacote=pacote,
                    )
                    total_decisoes += 1
                    if fechamento.acao == DecisaoIrrigacao.Acao.FECHAR:
                        executar_decisao(fechamento, 0, round(fluxo * duracao, 2), agora=fim)
                        estado = 'inativa'
                        total_irrigacoes += 1
                elif decisao.acao == DecisaoIrrigacao.Acao.FECHAR:
                    executar_decisao(decisao, 0, 0, agora=momento)
                    estado = 'inativa'
                    total_irrigacoes += 1
                elif momento == momentos[0]:
                    self._registrar_irrigacao(mesa, valvula, momento, 'inativa', 0, 0, 'válvula fechada no início')
                    total_irrigacoes += 1

        return total_leituras, total_irrigacoes, total_decisoes

    def _registrar_irrigacao(self, mesa, valvula, quando, status, fluxo, consumo, motivo):
        RegistroIrrigacao.objects.create(
            mesa_id=mesa, valvula_id=valvula, data_registro=quando, status_atual=status,
            fluxo_l_min=fluxo, consumo_ciclo_l=consumo, simulado=True,
            observacoes=f'{PREFIXO_SIMULADO} {motivo}',
        )
