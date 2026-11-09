from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from configuracao.previsao import PrevisaoChuva
from estufa.models import Estufa
from mesa.models import Mesa
from registroClima.ia.servico import decidir_mesa, decidir_todas
from registroClima.models import DecisaoIrrigacao, ModoIrrigacao, RegistroClima, RegistroIrrigacao

URL_STATUS = '/api/irrigacao/status/'
URL_DECISOES = '/api/irrigacao/decisoes-ia/'
URL_MODO = '/api/irrigacao/modo/'
URL_AVALIAR = '/api/irrigacao/avaliar/'

SEM_CHUVA = PrevisaoChuva(0.0, 5, 6, True, 'Rio Claro - São Paulo')
CHUVA_FORTE = PrevisaoChuva(14.0, 90, 6, True, 'Rio Claro - São Paulo')
SEM_CIDADE = PrevisaoChuva(0.0, None, 6, False, None,
                           'Cidade da propriedade não configurada; previsão de chuva considerada 0 mm.')


class BaseIrrigacaoIA(APITestCase):
    def setUp(self):
        estufa = Estufa.objects.create(nome_setor='Estufa A', tipo_cultivo='Hidroponia', capacidade_maxima=100)
        self.mesa = Mesa.objects.create(estufa=estufa, identificacao='A1', capacidade_maxima=10)
        self.mesa2 = Mesa.objects.create(estufa=estufa, identificacao='A2', capacidade_maxima=10)
        # Mesa fora de estufa (como a NF-AUTO) não tem válvula
        Mesa.objects.create(estufa=None, identificacao='NF-AUTO', capacidade_maxima=0)

        User = get_user_model()
        self.operador = User.objects.create_user('operador', password='x')
        self.gerente = User.objects.create_user('gerente', password='x')
        self.gerente.groups.add(Group.objects.create(name='Gerente'))

        patcher = mock.patch('registroClima.ia.servico.previsao_chuva', return_value=SEM_CHUVA)
        self.previsao = patcher.start()
        self.addCleanup(patcher.stop)
        patcher_view = mock.patch('registroClima.views.previsao_chuva', return_value=SEM_CHUVA)
        patcher_view.start()
        self.addCleanup(patcher_view.stop)

    def leitura(self, mesa=None, solo=60, temperatura=25, umidade=70, simulado=False):
        return RegistroClima.objects.create(
            mesa_id=mesa or self.mesa, temperatura=temperatura, umidade=umidade, luminosidade=20000,
            ventilacao=30, umidade_solo=solo, simulado=simulado,
        )

    def valvula(self, status, mesa=None):
        return RegistroIrrigacao.objects.create(mesa_id=mesa or self.mesa, valvula_id='VLV-A1', status_atual=status)

    def automatico(self):
        ModoIrrigacao.objects.update_or_create(pk=1, defaults={'modo': ModoIrrigacao.Modo.AUTOMATICO_IA})


class DecisaoDaMesaTests(BaseIrrigacaoIA):
    def test_sem_leitura_de_solo_nao_decide(self):
        RegistroClima.objects.create(mesa_id=self.mesa, temperatura=25, umidade=70, luminosidade=1, ventilacao=1)
        self.assertIsNone(decidir_mesa(self.mesa))
        self.assertFalse(DecisaoIrrigacao.objects.exists())

    def test_manual_so_sugere(self):
        self.leitura(solo=25)
        decisao = decidir_mesa(self.mesa)
        self.assertEqual(decisao.acao, DecisaoIrrigacao.Acao.ABRIR)
        self.assertEqual(decisao.modo, 'MANUAL')
        self.assertFalse(decisao.executada)
        self.assertFalse(RegistroIrrigacao.objects.exists())
        self.assertEqual(decisao.valvula_id, f'VLV-{self.mesa.id:02d}')
        self.assertIn('umidade do solo', decisao.justificativa)
        self.assertGreater(decisao.confianca, 0.9)

    def test_automatico_abre_a_valvula(self):
        self.automatico()
        self.valvula('inativa')
        self.leitura(solo=25, simulado=True)
        decisao = decidir_mesa(self.mesa)
        self.assertTrue(decisao.executada)
        registro = decisao.registro_irrigacao
        self.assertEqual(registro.status_atual, 'ativa')
        self.assertEqual(registro.valvula_id, 'VLV-A1')
        self.assertTrue(registro.simulado)
        self.assertTrue(registro.observacoes.startswith('[SIMULADO] [IA] Abrir válvula'))

    def test_automatico_fecha_com_solo_umido(self):
        self.automatico()
        self.valvula('ativa')
        self.leitura(solo=80)
        decisao = decidir_mesa(self.mesa)
        self.assertEqual(decisao.acao, DecisaoIrrigacao.Acao.FECHAR)
        self.assertEqual(decisao.registro_irrigacao.status_atual, 'inativa')
        self.assertTrue(decisao.registro_irrigacao.observacoes.startswith('[IA] Fechar'))

    def test_manter_nao_gera_comando(self):
        self.automatico()
        self.valvula('ativa')
        self.leitura(solo=55)  # faixa intermediária com válvula aberta: segue irrigando
        decisao = decidir_mesa(self.mesa)
        self.assertEqual(decisao.acao, DecisaoIrrigacao.Acao.MANTER_ABERTA)
        self.assertTrue(decisao.valvula_estava_aberta)
        self.assertFalse(decisao.executada)
        self.assertEqual(RegistroIrrigacao.objects.count(), 1)

    def test_chuva_prevista_segura_a_abertura(self):
        self.leitura(solo=35)
        decisao = decidir_mesa(self.mesa, previsao=CHUVA_FORTE)
        self.assertEqual(decisao.acao, DecisaoIrrigacao.Acao.MANTER_FECHADA)
        self.assertEqual(float(decisao.chuva_prevista_mm), 14.0)
        self.assertIn('chuva prevista', decisao.justificativa)

    def test_sem_cidade_explica_na_justificativa(self):
        self.leitura(solo=25)
        decisao = decidir_mesa(self.mesa, previsao=SEM_CIDADE)
        self.assertFalse(decisao.previsao_disponivel)
        self.assertIn('Cidade da propriedade não configurada', decisao.justificativa)

    def test_decidir_todas_ignora_mesa_sem_estufa_e_sem_leitura(self):
        self.leitura(solo=25)
        decisoes = decidir_todas()
        self.assertEqual([d.mesa_id for d in decisoes], [self.mesa])
        self.previsao.assert_called_once()


class RotasIrrigacaoIATests(BaseIrrigacaoIA):
    def test_status(self):
        self.valvula('inativa')
        self.leitura(solo=25)
        decidir_mesa(self.mesa)
        self.client.force_authenticate(self.operador)
        resposta = self.client.get(URL_STATUS)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data['modo'], 'MANUAL')
        self.assertFalse(resposta.data['pode_alterar_modo'])
        self.assertFalse(resposta.data['localizacao_configurada'])
        self.assertEqual(resposta.data['previsao_chuva']['chuva_mm'], 0.0)
        valvulas = {v['mesa']: v for v in resposta.data['valvulas']}
        self.assertEqual(set(valvulas), {'A1', 'A2'})
        self.assertEqual(valvulas['A1']['valvula_id'], 'VLV-A1')
        self.assertEqual(valvulas['A1']['umidade_solo'], 25.0)
        self.assertEqual(valvulas['A1']['ultima_decisao']['acao'], 'abrir')
        self.assertIsNone(valvulas['A2']['ultima_decisao'])

    def test_decisoes_no_formato_do_front(self):
        self.leitura(solo=25)
        self.leitura(mesa=self.mesa2, solo=80)
        decidir_todas()
        self.client.force_authenticate(self.operador)
        resposta = self.client.get(URL_DECISOES)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.data), 2)
        d = resposta.data[0]
        for campo in ('horario', 'valvula', 'acao', 'acao_nome', 'confianca', 'justificativa', 'entradas'):
            self.assertIn(campo, d)
        self.assertIsInstance(d['confianca'], float)
        self.assertLessEqual(d['confianca'], 1)

        filtrada = self.client.get(URL_DECISOES, {'mesa': self.mesa2.id, 'limite': 5})
        self.assertEqual([x['mesa'] for x in filtrada.data], ['A2'])
        self.assertEqual(self.client.get(URL_DECISOES, {'mesa': 'abc'}).status_code, 400)

        mudancas = self.client.get(URL_DECISOES, {'so_mudancas': '1'})
        self.assertEqual([x['acao'] for x in mudancas.data], ['abrir'])

    def test_modo_restrito_a_gerente(self):
        self.client.force_authenticate(self.operador)
        self.assertEqual(self.client.post(URL_MODO, {'modo': 'AUTOMATICO_IA'}).status_code, 403)

        self.client.force_authenticate(self.gerente)
        resposta = self.client.post(URL_MODO, {'modo': 'AUTOMATICO_IA'})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data['modo'], 'AUTOMATICO_IA')
        self.assertEqual(ModoIrrigacao.atual().atualizado_por, self.gerente)
        self.assertEqual(self.client.post(URL_MODO, {'modo': 'TURBO'}).status_code, 400)

    def test_avaliar_agora(self):
        self.leitura(solo=25)
        self.client.force_authenticate(self.operador)
        self.assertEqual(self.client.post(URL_AVALIAR).status_code, 403)

        self.client.force_authenticate(self.gerente)
        resposta = self.client.post(URL_AVALIAR)
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.data[0]['acao'], 'abrir')

    def test_rotas_exigem_login(self):
        for url in (URL_STATUS, URL_DECISOES):
            self.assertEqual(self.client.get(url).status_code, 401)
