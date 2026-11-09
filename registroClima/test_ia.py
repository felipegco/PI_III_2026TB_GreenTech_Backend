from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import numpy as np
from django.core.management import call_command
from django.test import SimpleTestCase

from registroClima.ia import modelo as ia
from registroClima.ia.dados import FEATURES, gerar_dataset, regra_agronomica


class DatasetSinteticoTests(SimpleTestCase):
    def test_reproduzivel_pela_semente(self):
        X1, y1 = gerar_dataset(500, seed=7)
        X2, y2 = gerar_dataset(500, seed=7)
        np.testing.assert_array_equal(X1, X2)
        np.testing.assert_array_equal(y1, y2)
        self.assertEqual(X1.shape, (500, len(FEATURES)))

    def test_tem_as_duas_classes_em_proporcao_razoavel(self):
        _, y = gerar_dataset(4000)
        self.assertGreater(y.mean(), 0.25)
        self.assertLess(y.mean(), 0.75)

    def test_regras_agronomicas(self):
        self.assertEqual(regra_agronomica(25, 25, 70, 20, 0), 1)  # crítico irriga mesmo com chuva
        self.assertEqual(regra_agronomica(35, 25, 70, 10, 0), 0)  # chuva prevista repõe
        self.assertEqual(regra_agronomica(35, 25, 70, 0, 0), 1)
        self.assertEqual(regra_agronomica(55, 25, 70, 0, 1), 1)   # histerese: segue irrigando
        self.assertEqual(regra_agronomica(55, 25, 70, 0, 0), 0)
        self.assertEqual(regra_agronomica(45, 34, 40, 0, 0), 1)   # calor e ar seco antecipam
        self.assertEqual(regra_agronomica(70, 35, 30, 0, 1), 0)


class ArvoreDeIrrigacaoTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pacote = ia.treinar()

    def prever(self, **leitura):
        return ia.prever(pacote=self.pacote, **leitura)

    def test_acuracia_no_conjunto_de_teste(self):
        self.assertGreaterEqual(self.pacote['metricas']['acuracia_teste'], 0.95)

    def test_solo_seco_irriga_com_confianca(self):
        d = self.prever(umidade_solo=22, temperatura=28, umidade_ar=60)
        self.assertTrue(d.irrigar)
        self.assertEqual(d.acao, 'irrigar')
        self.assertGreater(d.confianca, 0.9)
        self.assertIn('umidade do solo', d.justificativa)
        self.assertTrue(d.justificativa.startswith('Irrigar:'))

    def test_solo_encharcado_nao_irriga(self):
        d = self.prever(umidade_solo=85, temperatura=30, umidade_ar=50, valvula_aberta=True)
        self.assertFalse(d.irrigar)
        self.assertEqual(d.acao, 'nao_irrigar')
        self.assertTrue(d.justificativa.startswith('Não irrigar:'))

    def test_chuva_prevista_segura_a_irrigacao(self):
        seco = self.prever(umidade_solo=35, temperatura=25, umidade_ar=70, chuva_prevista_mm=0)
        chuva = self.prever(umidade_solo=35, temperatura=25, umidade_ar=70, chuva_prevista_mm=15)
        self.assertTrue(seco.irrigar)
        self.assertFalse(chuva.irrigar)
        self.assertIn('chuva prevista', chuva.justificativa)

    def test_histerese_pela_valvula(self):
        fechada = self.prever(umidade_solo=55, temperatura=25, umidade_ar=70, valvula_aberta=False)
        aberta = self.prever(umidade_solo=55, temperatura=25, umidade_ar=70, valvula_aberta=True)
        self.assertFalse(fechada.irrigar)
        self.assertTrue(aberta.irrigar)
        self.assertIn('válvula já estava aberta', aberta.justificativa)

    def test_confianca_cai_perto_do_limite(self):
        longe = self.prever(umidade_solo=20, temperatura=25, umidade_ar=70)
        perto = self.prever(umidade_solo=40, temperatura=25, umidade_ar=70)
        self.assertLess(perto.confianca, longe.confianca)
        self.assertGreaterEqual(perto.confianca, 0.5)

    def test_justificativa_so_tem_condicoes_que_decidem(self):
        d = self.prever(umidade_solo=22, temperatura=28, umidade_ar=60)
        # Solo crítico decide sozinho: temperatura e ar não entram na explicação
        self.assertNotIn('temperatura', d.justificativa)
        self.assertNotIn('umidade do ar', d.justificativa)
        self.assertIn('lido 22,0 %', d.justificativa)


class PersistenciaDoModeloTests(SimpleTestCase):
    def setUp(self):
        ia._cache.clear()
        self.addCleanup(ia._cache.clear)

    def test_modelo_versionado_carrega_com_a_versao_atual(self):
        self.assertTrue(ia.CAMINHO_MODELO.exists(), 'Rode python manage.py treinar_irrigacao')
        pacote = ia.carregar_modelo()
        self.assertEqual(pacote['features'], FEATURES)
        self.assertIn('acuracia_teste', pacote['metricas'])

    def test_sem_arquivo_treina_em_memoria(self):
        with TemporaryDirectory() as pasta, self.assertLogs('registroClima.ia.modelo', 'WARNING'):
            pacote = ia.carregar_modelo(Path(pasta) / 'nao_existe.joblib')
        self.assertIn('modelo', pacote)

    def test_versao_diferente_do_sklearn_retreina(self):
        with TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'antigo.joblib'
            antigo = ia.treinar(amostras=300)
            antigo['sklearn'] = '0.0.0'
            ia.joblib.dump(antigo, caminho)
            ia._cache.clear()
            with self.assertLogs('registroClima.ia.modelo', 'WARNING'):
                pacote = ia.carregar_modelo(caminho)
        self.assertNotEqual(pacote['sklearn'], '0.0.0')

    def test_comando_treina_e_salva(self):
        saida = StringIO()
        with mock.patch('registroClima.management.commands.treinar_irrigacao.salvar') as salvar:
            call_command('treinar_irrigacao', '--amostras', '800', stdout=saida)
        self.assertIn('Acurácia no teste', saida.getvalue())
        salvar.assert_called_once()
        self.assertIn('modelo', salvar.call_args.args[0])

    def test_comando_dry_run_nao_salva(self):
        with mock.patch('registroClima.management.commands.treinar_irrigacao.salvar') as salvar:
            call_command('treinar_irrigacao', '--amostras', '800', '--dry-run', stdout=StringIO())
        salvar.assert_not_called()
