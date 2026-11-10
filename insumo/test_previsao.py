from datetime import timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from funcionarios.models import Funcionario
from insumo.models import Insumo, MovimentacaoInsumo, PrevisaoEstoque
from insumo.previsao import (HORIZONTE_DIAS, calcular, dias_ate_consumir, percentual_restante, previsoes,
                             projetar, serie_consumo)

URL = '/api/estoque/previsao-prophet/'


class BasePrevisao:
    def setUp(self):
        self.funcionario = Funcionario.objects.create(nome_completo='Operador', cpf='111.111.111-11')
        self.hoje = timezone.localdate()

    def insumo(self, nome='Nitrato de Cálcio', saldo=0.0, minimo=0.0):
        return Insumo.objects.create(nome=nome, tipo='FE', unidade='kg', quantidade_atual=saldo,
                                     estoque_minimo=minimo)

    def mov(self, insumo, tipo, quantidade, dias_atras):
        mov = MovimentacaoInsumo.objects.create(insumo_id=insumo, funcionario_id=self.funcionario,
                                                tipo_movimentacao=tipo, quantidade=quantidade)
        quando = timezone.now() - timedelta(days=dias_atras)
        MovimentacaoInsumo.objects.filter(pk=mov.pk).update(data_movimentacao=quando)
        return mov

    def historico(self, insumo, dias, consumo_dia, compra):
        """Compra no primeiro dia e consumo diário constante; deixa o saldo coerente com as movimentações."""
        self.mov(insumo, 'Entrada', compra, dias)
        for d in range(dias - 1, 0, -1):
            self.mov(insumo, 'Saída', consumo_dia, d)
        insumo.quantidade_atual = compra - consumo_dia * (dias - 1)
        insumo.save()
        return insumo


class CalculoTests(BasePrevisao, TestCase):
    def test_dias_ate_consumir(self):
        self.assertEqual(dias_ate_consumir([2.0] * 10, 5), 3)
        self.assertEqual(dias_ate_consumir([2.0] * 10, 0), 0)
        self.assertIsNone(dias_ate_consumir([0.0] * 10, 5))

    def test_serie_diaria_soma_saida_e_perda_com_zeros(self):
        insumo = self.insumo()
        self.mov(insumo, 'Entrada', 30, 5)
        self.mov(insumo, 'Saída', 2, 3)
        self.mov(insumo, 'Perda', 1, 3)
        self.mov(insumo, 'Ajuste', 4, 1)
        serie = serie_consumo(insumo)
        self.assertEqual(len(serie), 6)
        self.assertEqual(serie[self.hoje - timedelta(days=3)], 3.0)
        self.assertEqual(sum(serie.values()), 3.0)

    def test_sem_consumo(self):
        insumo = self.insumo(saldo=10)
        self.mov(insumo, 'Entrada', 10, 30)
        previsao = calcular(insumo)
        self.assertEqual(previsao.modelo, 'sem_consumo')
        self.assertIsNone(previsao.dias_restantes)
        self.assertIsNone(previsao.data_esgotamento)

    def test_historico_curto_usa_media_movel(self):
        insumo = self.historico(self.insumo(), dias=8, consumo_dia=1.0, compra=20)
        previsao = calcular(insumo)
        self.assertEqual(previsao.modelo, 'media_movel')
        self.assertIn('Histórico curto', previsao.observacao)
        # 13 kg com 7 kg consumidos em 9 dias de série (o dia da compra e hoje não tiveram saída)
        self.assertEqual(previsao.dias_restantes, 17)
        self.assertEqual(previsao.data_esgotamento, self.hoje + timedelta(days=17))

    def test_prophet_com_historico_suficiente(self):
        insumo = self.historico(self.insumo(minimo=10), dias=60, consumo_dia=0.5, compra=50)
        previsao = calcular(insumo)
        self.assertEqual(previsao.modelo, 'prophet')
        self.assertAlmostEqual(previsao.consumo_medio_diario, 0.5, delta=0.05)
        # 20,5 kg a 0,5 kg/dia: cerca de 41 dias; o mínimo de 10 kg chega cerca de 20 dias antes
        self.assertAlmostEqual(previsao.dias_restantes, 41, delta=3)
        self.assertAlmostEqual(previsao.dias_restantes - previsao.dias_ate_minimo, 20, delta=2)

    def test_prophet_percebe_consumo_em_alta(self):
        constante = self.historico(self.insumo('Constante'), dias=60, consumo_dia=1.0, compra=100)
        crescente = self.insumo('Crescente')
        self.mov(crescente, 'Entrada', 100, 60)
        for d in range(59, 0, -1):
            self.mov(crescente, 'Saída', round(0.5 + (59 - d) / 58, 3), d)  # de 0,5 a 1,5 kg/dia
        crescente.quantidade_atual = constante.quantidade_atual
        crescente.save()
        self.assertLess(calcular(crescente).dias_restantes, calcular(constante).dias_restantes)

    def test_prophet_indisponivel_cai_para_media_movel(self):
        insumo = self.historico(self.insumo(), dias=30, consumo_dia=1.0, compra=60)
        with mock.patch('insumo.previsao._projetar_prophet', side_effect=ImportError('No module named prophet')), \
                self.assertLogs('insumo.previsao', 'WARNING'):
            previsao = calcular(insumo)
        self.assertEqual(previsao.modelo, 'media_movel')
        self.assertIn('Prophet indisponível', previsao.observacao)

    def test_insumo_esgotado(self):
        insumo = self.historico(self.insumo(), dias=10, consumo_dia=2.0, compra=18)
        previsao = calcular(insumo)
        self.assertEqual(previsao.dias_restantes, 0)
        self.assertEqual(previsao.percentual_restante, 0.0)

    def test_percentual_em_relacao_a_ultima_compra(self):
        insumo = self.historico(self.insumo(), dias=11, consumo_dia=2.0, compra=40)
        self.assertEqual(percentual_restante(insumo), 50.0)

    def test_projecao_nunca_negativa(self):
        serie = {self.hoje - timedelta(days=i): (5.0 if i > 20 else 0.1) for i in range(40, -1, -1)}
        projecao = projetar(serie)
        self.assertEqual(len(projecao.consumo_diario), HORIZONTE_DIAS)
        self.assertGreaterEqual(min(projecao.consumo_diario), 0)


class CacheTests(BasePrevisao, TestCase):
    def test_reaproveita_ate_o_insumo_se_movimentar(self):
        insumo = self.historico(self.insumo(), dias=8, consumo_dia=1.0, compra=20)
        primeira = previsoes()[0]
        with mock.patch('insumo.previsao.calcular') as calc:
            previsoes()
            calc.assert_not_called()

        self.mov(insumo, 'Saída', 1, 0)
        insumo.quantidade_atual -= 1
        insumo.save()
        segunda = previsoes()[0]
        self.assertGreater(segunda.ultima_movimentacao_id, primeira.ultima_movimentacao_id)
        self.assertEqual(PrevisaoEstoque.objects.count(), 1)

    def test_mais_criticos_primeiro_e_sem_previsao_no_fim(self):
        self.historico(self.insumo('Folgado'), dias=8, consumo_dia=0.1, compra=20)
        self.historico(self.insumo('Crítico'), dias=8, consumo_dia=2.0, compra=20)
        parado = self.insumo('Parado', saldo=5)
        self.mov(parado, 'Entrada', 5, 3)
        self.assertEqual([p.insumo.nome for p in previsoes()], ['Crítico', 'Folgado', 'Parado'])


class RotaPrevisaoTests(BasePrevisao, APITestCase):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user('operador', password='x')

    def test_formato_do_widget(self):
        self.historico(self.insumo(minimo=5), dias=8, consumo_dia=1.0, compra=20)
        self.client.force_authenticate(self.user)
        resposta = self.client.get(URL)
        self.assertEqual(resposta.status_code, 200)
        item = resposta.data[0]
        for campo in ('id', 'nome', 'categoria', 'quantidadeAtual', 'unidade', 'diasRestantes',
                      'percentualRestante', 'dataEstimada', 'estoqueMinimoEm', 'modelo', 'modeloNome'):
            self.assertIn(campo, item)
        self.assertEqual(item['categoria'], 'Fertilizante')
        self.assertEqual(item['modelo'], 'media_movel')

    def test_limite_e_recalcular(self):
        self.historico(self.insumo('A'), dias=8, consumo_dia=1.0, compra=20)
        self.historico(self.insumo('B'), dias=8, consumo_dia=2.0, compra=20)
        self.client.force_authenticate(self.user)
        self.assertEqual([p['nome'] for p in self.client.get(URL, {'limite': 1}).data], ['B'])
        self.assertEqual(self.client.get(URL, {'limite': 'x'}).status_code, 400)
        with mock.patch('insumo.views.previsoes', return_value=[]) as prev:
            self.client.get(URL, {'recalcular': '1'})
            prev.assert_called_once_with(recalcular=True)

    def test_exige_login(self):
        self.assertEqual(self.client.get(URL).status_code, 401)


class ComandoTests(BasePrevisao, TestCase):
    def test_prever_estoque(self):
        insumo = self.historico(self.insumo(), dias=8, consumo_dia=1.0, compra=20)
        saida = StringIO()
        call_command('prever_estoque', stdout=saida)
        self.assertIn('Nitrato de Cálcio', saida.getvalue())
        self.assertIn('1 previsões atualizadas', saida.getvalue())
        call_command('prever_estoque', '--insumo', str(insumo.id), stdout=StringIO())
