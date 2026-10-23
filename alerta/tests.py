from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from alerta.models import Alerta
from alerta.services import FAIXA_PADRAO, avaliar_leitura, faixa_da_mesa, gerar_alertas
from cultura.models import Cultura
from estufa.models import Estufa
from lotePlantio.models import LotePlantio
from mesa.models import Mesa
from registroClima.models import RegistroClima

URL_INGESTAO = '/api/clima/receber_dados_iot/'
URL_ALERTAS = '/api/alertas/'


class BaseAlertaTests(APITestCase):

    def setUp(self):
        estufa = Estufa.objects.create(nome_setor='Estufa A', tipo_cultivo='Hidroponia', capacidade_maxima=100)
        self.mesa = Mesa.objects.create(estufa=estufa, identificacao='M1', capacidade_maxima=10)
        cultura = Cultura.objects.create(
            nome_cultura='Alface', tempo_medio_colheita=45,
            temperatura_minima=18, temperatura_maxima=26, umidade_ideal=65,
        )
        LotePlantio.objects.create(
            cultura_id=cultura, mesa_id=self.mesa, data_plantio=date.today(),
            status=LotePlantio.StatusPlantio.ATIVO,
        )

    def leitura(self, minutos_atras=0, **valores):
        dados = {'temperatura': 22, 'umidade': 65, 'luminosidade': 30000, 'ventilacao': 30, 'umidade_solo': 60}
        dados.update(valores)
        return RegistroClima.objects.create(
            mesa_id=self.mesa, data_registro=timezone.now() - timedelta(minutes=minutos_atras), **dados,
        )


class RegrasDeAlertaTests(BaseAlertaTests):

    def test_faixa_vem_da_cultura_ou_do_padrao(self):
        self.assertEqual(faixa_da_mesa(self.mesa), (
            {'temp_min': 18.0, 'temp_max': 26.0, 'umidade_ideal': 65.0}, False,
        ))
        outra = Mesa.objects.create(estufa=self.mesa.estufa, identificacao='M2', capacidade_maxima=10)
        self.assertEqual(faixa_da_mesa(outra), (FAIXA_PADRAO, True))

    def test_leitura_normal_nao_gera_alerta(self):
        self.assertEqual(gerar_alertas(self.leitura()), [])

    def test_gravidade_da_temperatura(self):
        faixa = faixa_da_mesa(self.mesa)[0]
        atencao = avaliar_leitura(self.leitura(temperatura=28), faixa)[0]
        critico = avaliar_leitura(self.leitura(temperatura=31), faixa)[0]
        frio = avaliar_leitura(self.leitura(temperatura=15), faixa)[0]
        self.assertEqual((atencao['gravidade'], critico['gravidade']), ('atencao', 'critico'))
        self.assertIn('acima do máximo', atencao['mensagem'])
        self.assertIn('abaixo do mínimo', frio['mensagem'])
        self.assertEqual(atencao['faixa_esperada'], '18°C a 26°C')

    def test_gravidade_da_umidade_e_do_solo(self):
        faixa = faixa_da_mesa(self.mesa)[0]
        por_parametro = {a['parametro']: a for a in avaliar_leitura(self.leitura(umidade=35, umidade_solo=20), faixa)}
        self.assertEqual(por_parametro['umidade']['gravidade'], 'critico')
        self.assertEqual(por_parametro['umidade_solo']['gravidade'], 'critico')
        self.assertEqual(por_parametro['umidade_solo']['acao_sugerida'], 'Acionar a irrigação da mesa.')
        # 16 pontos acima do ideal: só atenção
        self.assertEqual(avaliar_leitura(self.leitura(umidade=81), faixa)[0]['gravidade'], 'atencao')

    def test_leitura_sem_umidade_do_solo_ignora_esse_parametro(self):
        self.assertEqual(gerar_alertas(self.leitura(umidade_solo=None)), [])

    def test_mesma_anomalia_atualiza_o_alerta_aberto_em_vez_de_duplicar(self):
        primeiro = gerar_alertas(self.leitura(minutos_atras=10, temperatura=28))[0]
        segunda = self.leitura(temperatura=32)
        gerar_alertas(segunda)
        self.assertEqual(Alerta.objects.count(), 1)
        primeiro.refresh_from_db()
        self.assertEqual((primeiro.gravidade, float(primeiro.valor_lido)), ('critico', 32))
        self.assertEqual(primeiro.leitura, segunda)
        # data_hora guarda quando o problema começou; atualizado_em, a última ocorrência
        self.assertLess(primeiro.data_hora, primeiro.atualizado_em)

    def test_depois_de_resolvido_a_anomalia_abre_alerta_novo(self):
        alerta = gerar_alertas(self.leitura(temperatura=28))[0]
        alerta.status = Alerta.Status.RESOLVIDO
        alerta.save()
        gerar_alertas(self.leitura(temperatura=28))
        self.assertEqual(Alerta.objects.filter(status=Alerta.Status.ATIVO).count(), 1)
        self.assertEqual(Alerta.objects.count(), 2)


@override_settings(IOT_API_KEY='chave-teste')
class GeracaoNaIngestaoTests(BaseAlertaTests):

    def test_leitura_dos_sensores_gera_alerta(self):
        resp = self.client.post(URL_INGESTAO, {
            'mesa_id': self.mesa.pk, 'temperatura': 33, 'umidade': 65, 'luminosidade': 30000,
            'ventilacao': 30, 'simulado': True,
        }, format='json', HTTP_AUTHORIZATION='Api-Key chave-teste')
        self.assertEqual(resp.status_code, 201)
        alerta = Alerta.objects.get()
        self.assertEqual((alerta.parametro, alerta.gravidade), ('temperatura', 'critico'))

    def test_cadastro_manual_de_leitura_tambem_gera_alerta(self):
        self.client.force_authenticate(get_user_model().objects.create_user(username='op', password='x'))
        resp = self.client.post('/api/clima/', {
            'mesa_id': self.mesa.pk, 'temperatura': 22, 'umidade': 30, 'luminosidade': 30000, 'ventilacao': 30,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Alerta.objects.get().parametro, 'umidade')


class ApiAlertasTests(BaseAlertaTests):

    def setUp(self):
        super().setUp()
        self.usuario = get_user_model().objects.create_user(username='gerente', password='x')
        self.client.force_authenticate(self.usuario)
        gerar_alertas(self.leitura(minutos_atras=5, temperatura=31, simulado=True))
        gerar_alertas(self.leitura(umidade=45))

    def test_lista_no_formato_da_tela_de_alertas(self):
        resp = self.client.get(URL_ALERTAS)
        self.assertEqual(resp.status_code, 200)
        temperatura = next(a for a in resp.data if a['parametro'] == 'temperatura')
        self.assertEqual(temperatura['mesaIdentificacao'], 'M1')
        self.assertEqual(temperatura['parametroNome'], 'Temperatura')
        self.assertEqual(temperatura['valorLido'], '31.0 °C')
        self.assertEqual(temperatura['faixaEsperada'], '18°C a 26°C')
        self.assertEqual(temperatura['gravidade'], 'critico')
        self.assertFalse(temperatura['isPadrao'])
        self.assertTrue(temperatura['simulado'])
        self.assertTrue(temperatura['acaoSugerida'])
        for campo in ('id', 'mensagem', 'dataHora', 'status'):
            self.assertIn(campo, temperatura)

    def test_mais_recente_primeiro_e_filtros(self):
        self.assertEqual([a['parametro'] for a in self.client.get(URL_ALERTAS).data], ['umidade', 'temperatura'])
        self.assertEqual(len(self.client.get(URL_ALERTAS, {'gravidade': 'critico'}).data), 1)
        self.assertEqual(len(self.client.get(URL_ALERTAS, {'parametro': 'umidade'}).data), 1)
        self.assertEqual(len(self.client.get(URL_ALERTAS, {'mesa': self.mesa.pk}).data), 2)
        self.assertEqual(len(self.client.get(URL_ALERTAS, {'status': 'resolvido'}).data), 0)

    def test_resolver_alerta(self):
        alerta = Alerta.objects.get(parametro='temperatura')
        resp = self.client.patch(f'{URL_ALERTAS}{alerta.pk}/resolver/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual((resp.data['status'], resp.data['resolvidoPor']), ('resolvido', 'gerente'))
        self.assertIsNotNone(resp.data['resolvidoEm'])
        self.assertEqual(self.client.patch(f'{URL_ALERTAS}{alerta.pk}/resolver/').status_code, 400)
        self.assertEqual(len(self.client.get(URL_ALERTAS, {'status': 'ativo'}).data), 1)

    def test_alertas_nao_sao_criados_nem_apagados_pela_api(self):
        self.assertEqual(self.client.post(URL_ALERTAS, {}).status_code, 405)
        alerta = Alerta.objects.first()
        self.assertEqual(self.client.delete(f'{URL_ALERTAS}{alerta.pk}/').status_code, 405)

    def test_exige_autenticacao(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(URL_ALERTAS).status_code, 401)
