import random
from datetime import date, timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from cultura.models import Cultura
from estufa.models import Estufa
from lotePlantio.models import LotePlantio
from mesa.models import Mesa
from registroClima.management.commands.simular_irrigacao import (
    decidir, estado_atual, gerar_registro, valvula_da_mesa,
)
from registroClima.management.commands.simular_leituras import (
    FAIXA_PADRAO, faixa_da_mesa, gerar_leitura,
)
from registroClima.models import RegistroClima, RegistroIrrigacao

URL_INGESTAO = '/api/clima/receber_dados_iot/'
URL_IRRIGACAO = '/api/irrigacao/atualizar_status/'


def leitura_valida(mesa, **extra):
    return {
        'mesa_id': mesa.pk, 'temperatura': 24.5, 'umidade': 70, 'luminosidade': 32000,
        'ventilacao': 40, 'umidade_solo': 55, 'co2': 650, 'ph': 6.2, **extra,
    }


@override_settings(IOT_API_KEY='chave-teste')
class IngestaoIotTests(APITestCase):
    """A ingestão dos sensores usa a chave de API do ambiente, não JWT."""

    def setUp(self):
        estufa = Estufa.objects.create(nome_setor='Estufa A', tipo_cultivo='Hidroponia', capacidade_maxima=100)
        self.mesa = Mesa.objects.create(estufa=estufa, identificacao='M1', capacidade_maxima=10)

    def _enviar(self, payload, chave='chave-teste'):
        headers = {'HTTP_AUTHORIZATION': f'Api-Key {chave}'} if chave else {}
        return self.client.post(URL_INGESTAO, payload, format='json', **headers)

    def test_aceita_leitura_com_chave_correta(self):
        resp = self._enviar(leitura_valida(self.mesa))
        self.assertEqual(resp.status_code, 201)
        registro = RegistroClima.objects.get()
        self.assertEqual(float(registro.umidade_solo), 55)
        self.assertEqual(float(registro.luminosidade), 32000)
        # Sensor físico não envia o campo, então a leitura não é marcada como simulada
        self.assertFalse(registro.simulado)

    def test_recusa_chave_errada_ou_ausente(self):
        self.assertEqual(self._enviar(leitura_valida(self.mesa), chave='outra').status_code, 401)
        self.assertEqual(self._enviar(leitura_valida(self.mesa), chave=None).status_code, 401)
        self.assertFalse(RegistroClima.objects.exists())

    def test_recusa_chave_antiga_que_estava_no_codigo(self):
        resp = self._enviar(leitura_valida(self.mesa), chave='GT_IOT_SECRET_KEY_2026')
        self.assertEqual(resp.status_code, 401)

    @override_settings(IOT_API_KEY=None)
    def test_bloqueia_ingestao_sem_chave_configurada(self):
        self.assertEqual(self._enviar(leitura_valida(self.mesa), chave='').status_code, 401)

    def test_novos_sensores_sao_opcionais(self):
        payload = leitura_valida(self.mesa)
        for campo in ('umidade_solo', 'co2', 'ph'):
            payload.pop(campo)
        self.assertEqual(self._enviar(payload).status_code, 201)

    def test_valida_faixa_de_umidade_do_solo_e_ph(self):
        resp = self._enviar(leitura_valida(self.mesa, umidade_solo=120, ph=15))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('umidade_solo', resp.data)
        self.assertIn('ph', resp.data)


class ConsultaLeiturasTests(APITestCase):

    def setUp(self):
        user = get_user_model().objects.create_user(username='tester', password='x')
        self.client.force_authenticate(user)
        estufa = Estufa.objects.create(nome_setor='Estufa A', tipo_cultivo='Hidroponia', capacidade_maxima=100)
        self.m1 = Mesa.objects.create(estufa=estufa, identificacao='M1', capacidade_maxima=10)
        self.m2 = Mesa.objects.create(estufa=estufa, identificacao='M2', capacidade_maxima=10)
        agora = timezone.now()
        for mesa, minutos, temp in [(self.m1, 10, 20), (self.m1, 1, 21), (self.m2, 5, 30)]:
            RegistroClima.objects.create(
                mesa_id=mesa, data_registro=agora - timedelta(minutes=minutos),
                temperatura=temp, umidade=60, luminosidade=1000, ventilacao=30,
            )

    def test_lista_mais_recente_primeiro(self):
        datas = [r['data_registro'] for r in self.client.get('/api/clima/').data]
        self.assertEqual(datas, sorted(datas, reverse=True))

    def test_ultimas_traz_uma_leitura_por_mesa(self):
        resp = self.client.get('/api/clima/ultimas/')
        self.assertEqual(resp.status_code, 200)
        por_mesa = {r['mesa_id']: float(r['temperatura']) for r in resp.data}
        self.assertEqual(por_mesa, {self.m1.pk: 21, self.m2.pk: 30})

    def test_ultimas_exige_autenticacao(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/clima/ultimas/').status_code, 401)


class SimuladorLeiturasTests(APITestCase):

    def setUp(self):
        estufa = Estufa.objects.create(nome_setor='Estufa A', tipo_cultivo='Hidroponia', capacidade_maxima=100)
        self.mesa = Mesa.objects.create(estufa=estufa, identificacao='M1', capacidade_maxima=10)
        self.faixa = {'temp_min': 18.0, 'temp_max': 26.0, 'umidade_ideal': 65.0}

    def test_faixa_vem_da_cultura_do_lote_ativo(self):
        self.assertEqual(faixa_da_mesa(self.mesa), FAIXA_PADRAO)
        cultura = Cultura.objects.create(
            nome_cultura='Alface', tempo_medio_colheita=45,
            temperatura_minima=18, temperatura_maxima=26, umidade_ideal=65,
        )
        LotePlantio.objects.create(
            cultura_id=cultura, mesa_id=self.mesa, data_plantio=date.today(),
            status=LotePlantio.StatusPlantio.ATIVO,
        )
        self.assertEqual(faixa_da_mesa(self.mesa), self.faixa)

    def test_cenario_normal_fica_dentro_da_faixa(self):
        rng = random.Random(1)
        for _ in range(50):
            leitura = gerar_leitura(self.mesa.pk, self.faixa, 'normal', rng)
            self.assertTrue(18 <= leitura['temperatura'] <= 26)
            self.assertTrue(45 <= leitura['umidade_solo'] <= 75)

    def test_cenarios_de_anomalia_saem_da_faixa(self):
        rng = random.Random(1)
        self.assertGreater(gerar_leitura(self.mesa.pk, self.faixa, 'calor', rng)['temperatura'], 26)
        self.assertLess(gerar_leitura(self.mesa.pk, self.faixa, 'frio', rng)['temperatura'], 18)
        self.assertLess(gerar_leitura(self.mesa.pk, self.faixa, 'ar_seco', rng)['umidade'], 45)
        self.assertLess(gerar_leitura(self.mesa.pk, self.faixa, 'solo_seco', rng)['umidade_solo'], 30)

    @override_settings(IOT_API_KEY='chave-teste')
    def test_leitura_gerada_e_aceita_pela_api(self):
        for cenario in ('normal', 'calor', 'frio', 'ar_seco', 'solo_seco', 'aleatorio'):
            leitura = gerar_leitura(self.mesa.pk, FAIXA_PADRAO, cenario, random.Random(2))
            resp = self.client.post(URL_INGESTAO, leitura, format='json', HTTP_AUTHORIZATION='Api-Key chave-teste')
            self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(RegistroClima.objects.filter(simulado=False).exists())
        self.assertTrue(all(r.observacoes.startswith('[SIMULADO]') for r in RegistroClima.objects.all()))

    def test_dry_run_nao_envia_nada(self):
        saida = StringIO()
        call_command('simular_leituras', '--dry-run', '--seed', '3', stdout=saida)
        self.assertIn('"mesa_id": %d' % self.mesa.pk, saida.getvalue())
        self.assertFalse(RegistroClima.objects.exists())


class SimuladorIrrigacaoTests(APITestCase):

    def setUp(self):
        estufa = Estufa.objects.create(nome_setor='Estufa A', tipo_cultivo='Hidroponia', capacidade_maxima=100)
        self.mesa = Mesa.objects.create(estufa=estufa, identificacao='M1', capacidade_maxima=10)

    def _leitura_solo(self, umidade_solo):
        RegistroClima.objects.create(
            mesa_id=self.mesa, temperatura=22, umidade=65, luminosidade=30000, ventilacao=30,
            umidade_solo=umidade_solo,
        )

    def test_decide_com_histerese(self):
        self.assertEqual(decidir(30, 'inativa')[0], 'ativa')
        self.assertEqual(decidir(80, 'ativa')[0], 'inativa')
        # Entre os limites o estado anterior é mantido
        self.assertEqual(decidir(50, 'ativa')[0], 'ativa')
        self.assertEqual(decidir(50, 'inativa')[0], 'inativa')
        self.assertEqual(decidir(None, 'ativa')[0], 'inativa')

    def test_modos_forcados_ignoram_o_solo(self):
        self.assertEqual(decidir(90, 'inativa', 'abrir')[0], 'ativa')
        self.assertEqual(decidir(10, 'ativa', 'fechar')[0], 'inativa')

    def test_estado_usa_ultima_leitura_do_solo_e_ultima_valvula(self):
        self.assertEqual(estado_atual(self.mesa), ('inativa', None))
        self.assertEqual(valvula_da_mesa(self.mesa), f'VLV-{self.mesa.pk:02d}')
        self._leitura_solo(25)
        RegistroIrrigacao.objects.create(mesa_id=self.mesa, valvula_id='VLV-A', status_atual='ativa')
        self.assertEqual(estado_atual(self.mesa), ('ativa', 25.0))
        self.assertEqual(valvula_da_mesa(self.mesa), 'VLV-A')

    def test_valvula_fechada_nao_tem_vazao_nem_consumo(self):
        registro = gerar_registro(self.mesa.pk, 'VLV-01', 'inativa', 'teste', 5, random.Random(1))
        self.assertEqual((registro['fluxo_l_min'], registro['consumo_ciclo_l']), (0.0, 0))
        aberta = gerar_registro(self.mesa.pk, 'VLV-01', 'ativa', 'teste', 5, random.Random(1))
        self.assertAlmostEqual(aberta['consumo_ciclo_l'], aberta['fluxo_l_min'] * 5, places=1)

    @override_settings(IOT_API_KEY='chave-teste')
    def test_registro_gerado_e_aceito_e_marcado_como_simulado(self):
        self._leitura_solo(20)
        status, motivo = decidir(*reversed(estado_atual(self.mesa)))
        registro = gerar_registro(self.mesa.pk, valvula_da_mesa(self.mesa), status, motivo, 5, random.Random(1))
        resp = self.client.post(URL_IRRIGACAO, registro, format='json', HTTP_AUTHORIZATION='Api-Key chave-teste')
        self.assertEqual(resp.status_code, 201, resp.data)
        salvo = RegistroIrrigacao.objects.get()
        self.assertEqual(salvo.status_atual, 'ativa')
        self.assertTrue(salvo.simulado)
        self.assertTrue(salvo.observacoes.startswith('[SIMULADO]'))

    def test_dry_run_nao_envia_nada(self):
        self._leitura_solo(20)
        saida = StringIO()
        call_command('simular_irrigacao', '--dry-run', '--seed', '3', stdout=saida)
        self.assertIn('"status_atual": "ativa"', saida.getvalue())
        self.assertFalse(RegistroIrrigacao.objects.exists())
