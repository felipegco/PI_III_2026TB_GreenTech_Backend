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
from registroClima.management.commands.simular_leituras import (
    FAIXA_PADRAO, faixa_da_mesa, gerar_leitura,
)
from registroClima.models import RegistroClima

URL_INGESTAO = '/api/clima/receber_dados_iot/'


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

    def test_dry_run_nao_envia_nada(self):
        saida = StringIO()
        call_command('simular_leituras', '--dry-run', '--seed', '3', stdout=saida)
        self.assertIn('"mesa_id": %d' % self.mesa.pk, saida.getvalue())
        self.assertFalse(RegistroClima.objects.exists())
