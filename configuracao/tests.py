import json
import urllib.error
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from rest_framework.test import APITestCase

from .models import LocalizacaoPropriedade

URL_LOCALIZACAO = '/api/configuracao/localizacao/'
URL_CIDADES = '/api/configuracao/cidades/'

MOGI = {
    'cidade': 'Mogi Guaçu', 'estado': 'São Paulo', 'pais': 'Brasil',
    'latitude': -22.3677, 'longitude': -46.94552, 'fuso_horario': 'America/Sao_Paulo',
}

RESPOSTA_OPEN_METEO = {'results': [{
    'name': 'Mogi Guaçu', 'admin1': 'São Paulo', 'country': 'Brasil', 'latitude': -22.3677,
    'longitude': -46.94552, 'timezone': 'America/Sao_Paulo', 'population': 160318,
}]}


class RespostaFalsa:
    def __init__(self, corpo):
        self.corpo = json.dumps(corpo).encode()

    def read(self):
        return self.corpo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class LocalizacaoTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.operador = User.objects.create_user('operador', password='x')
        self.gerente = User.objects.create_user('gerente', password='x', first_name='Carla')
        self.gerente.groups.add(Group.objects.create(name='Gerente'))

    def test_sem_cidade_informa_que_falta_configurar(self):
        self.client.force_authenticate(self.operador)
        resposta = self.client.get(URL_LOCALIZACAO)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.data['configurada'])
        self.assertIsNone(resposta.data['localizacao'])
        self.assertFalse(resposta.data['pode_editar'])

    def test_gerente_grava_e_regrava_a_mesma_linha(self):
        self.client.force_authenticate(self.gerente)
        resposta = self.client.put(URL_LOCALIZACAO, MOGI, format='json')
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.data['configurada'])
        self.assertTrue(resposta.data['pode_editar'])
        self.assertEqual(resposta.data['localizacao']['cidade'], 'Mogi Guaçu')
        self.assertEqual(resposta.data['localizacao']['atualizado_por_nome'], 'Carla')

        outra = dict(MOGI, cidade='Araras', latitude=-22.357, longitude=-47.384)
        self.client.put(URL_LOCALIZACAO, outra, format='json')
        self.assertEqual(LocalizacaoPropriedade.objects.count(), 1)
        self.assertEqual(LocalizacaoPropriedade.atual().cidade, 'Araras')

    def test_operador_nao_altera(self):
        self.client.force_authenticate(self.operador)
        resposta = self.client.put(URL_LOCALIZACAO, MOGI, format='json')
        self.assertEqual(resposta.status_code, 403)
        self.assertIsNone(LocalizacaoPropriedade.atual())

    def test_coordenadas_invalidas(self):
        self.client.force_authenticate(self.gerente)
        resposta = self.client.put(URL_LOCALIZACAO, dict(MOGI, latitude=-95), format='json')
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('latitude', resposta.data)

    def test_exige_login(self):
        self.assertEqual(self.client.get(URL_LOCALIZACAO).status_code, 401)


class BuscaCidadesTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client.force_authenticate(get_user_model().objects.create_user('u', password='x'))

    @mock.patch('configuracao.geocoding.urllib.request.urlopen')
    def test_traduz_resposta_da_open_meteo_e_usa_cache(self, urlopen):
        urlopen.return_value = RespostaFalsa(RESPOSTA_OPEN_METEO)
        resposta = self.client.get(URL_CIDADES, {'q': 'Mogi Guaçu'})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data[0]['cidade'], 'Mogi Guaçu')
        self.assertEqual(resposta.data[0]['estado'], 'São Paulo')
        self.assertEqual(resposta.data[0]['latitude'], -22.3677)
        self.assertIn('countryCode=BR', urlopen.call_args.args[0])

        self.client.get(URL_CIDADES, {'q': '  mogi   guaçu '})
        self.assertEqual(urlopen.call_count, 1)

    @mock.patch('configuracao.geocoding.urllib.request.urlopen')
    def test_sem_resultados(self, urlopen):
        urlopen.return_value = RespostaFalsa({'generationtime_ms': 0.1})
        resposta = self.client.get(URL_CIDADES, {'q': 'xyzxyz'})
        self.assertEqual(resposta.data, [])

    def test_termo_curto(self):
        self.assertEqual(self.client.get(URL_CIDADES, {'q': 'mo'}).status_code, 400)

    @mock.patch('configuracao.geocoding.urllib.request.urlopen', side_effect=urllib.error.URLError('offline'))
    def test_servico_fora_do_ar(self, _):
        resposta = self.client.get(URL_CIDADES, {'q': 'Mogi'})
        self.assertEqual(resposta.status_code, 503)


class PrevisaoChuvaTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def configurar(self):
        return LocalizacaoPropriedade.objects.create(pk=1, **MOGI)

    @staticmethod
    def resposta_horaria(chuva, probabilidade):
        return RespostaFalsa({'hourly': {
            'time': [f'2026-11-09T{h:02d}:00' for h in range(len(chuva))],
            'precipitation': chuva, 'precipitation_probability': probabilidade,
        }})

    def test_sem_cidade_vale_zero_e_nao_consulta(self):
        from .previsao import previsao_chuva
        with mock.patch('configuracao.previsao.urllib.request.urlopen') as urlopen:
            previsao = previsao_chuva()
        urlopen.assert_not_called()
        self.assertEqual(previsao.chuva_mm, 0.0)
        self.assertFalse(previsao.disponivel)
        self.assertIn('não configurada', previsao.motivo)

    @mock.patch('configuracao.previsao.urllib.request.urlopen')
    def test_soma_as_proximas_horas_e_guarda_em_cache(self, urlopen):
        from .previsao import previsao_chuva
        self.configurar()
        urlopen.return_value = self.resposta_horaria([0, 0.4, 2.1, 3.0, None, 0.5], [10, 40, 80, 90, None, 30])
        previsao = previsao_chuva()
        self.assertTrue(previsao.disponivel)
        self.assertEqual(previsao.chuva_mm, 6.0)
        self.assertEqual(previsao.probabilidade_max, 90)
        self.assertEqual(previsao.cidade, 'Mogi Guaçu - São Paulo')
        url = urlopen.call_args.args[0]
        self.assertIn('forecast_hours=6', url)
        self.assertIn('latitude=-22.3677', url)

        previsao_chuva()
        self.assertEqual(urlopen.call_count, 1)

    @mock.patch('configuracao.previsao.urllib.request.urlopen', side_effect=urllib.error.URLError('offline'))
    def test_servico_fora_do_ar_vale_zero_sem_cache(self, urlopen):
        from .previsao import previsao_chuva
        self.configurar()
        with self.assertLogs('configuracao.previsao', 'WARNING'):
            previsao = previsao_chuva()
        self.assertEqual(previsao.chuva_mm, 0.0)
        self.assertFalse(previsao.disponivel)
        self.assertEqual(previsao.cidade, 'Mogi Guaçu - São Paulo')
        with self.assertLogs('configuracao.previsao', 'WARNING'):
            previsao_chuva()
        self.assertEqual(urlopen.call_count, 2)

    @mock.patch('configuracao.previsao.urllib.request.urlopen')
    def test_resposta_sem_dados_horarios(self, urlopen):
        from .previsao import previsao_chuva
        self.configurar()
        urlopen.return_value = RespostaFalsa({'error': True, 'reason': 'x'})
        with self.assertLogs('configuracao.previsao', 'WARNING'):
            self.assertFalse(previsao_chuva().disponivel)
