from datetime import date, timedelta

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from colheita.models import Colheita
from cultura.models import Cultura
from estufa.models import Estufa
from funcionarios.models import Funcionario
from lotePlantio.models import LotePlantio
from mesa.models import Mesa

URL = '/api/cultura/'
AT, CO = LotePlantio.StatusPlantio.ATIVO, LotePlantio.StatusPlantio.COLHIDO


class CulturaResumoTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(get_user_model().objects.create_user('gerente', password='x'))
        estufa = Estufa.objects.create(nome_setor='Estufa A', tipo_cultivo='NFT', capacidade_maxima=300)
        self.mesas = [Mesa.objects.create(estufa=estufa, identificacao=f'A{i}', capacidade_maxima=100)
                      for i in range(1, 4)]
        self.funcionario = Funcionario.objects.create(nome_completo='Operador', cpf='111.111.111-11')
        self.alface = Cultura.objects.create(nome_cultura='Alface', categoria='folhosa', tempo_medio_colheita=45,
                                             temperatura_minima=15, temperatura_maxima=24, umidade_ideal=70)

    def lote(self, mesa, dias_atras, status=AT):
        return LotePlantio.objects.create(cultura_id=self.alface, mesa_id=mesa, status=status, quantidade=50,
                                          data_plantio=date.today() - timedelta(days=dias_atras))

    def item(self):
        return next(c for c in self.client.get(URL).data if c['id'] == self.alface.id)

    def test_categoria_padrao_e_nome(self):
        Cultura.objects.create(nome_cultura='Sem categoria', tempo_medio_colheita=30, temperatura_minima=10,
                               temperatura_maxima=20, umidade_ideal=60)
        dados = {c['nome_cultura']: c for c in self.client.get(URL).data}
        self.assertEqual(dados['Alface']['categoria_nome'], 'Folhosa')
        self.assertEqual(dados['Sem categoria']['categoria'], 'outra')

    def test_sem_lotes_ativos(self):
        item = self.item()
        self.assertEqual(item['lotes_ativos'], 0)
        self.assertIsNone(item['proxima_colheita'])
        self.assertIsNone(item['mesa_proxima_colheita'])

    def test_proxima_colheita_pelo_lote_mais_antigo(self):
        self.lote(self.mesas[0], 10)
        self.lote(self.mesas[1], 30)
        self.lote(self.mesas[2], 60, status=CO)  # encerrado não conta
        item = self.item()
        self.assertEqual(item['lotes_ativos'], 2)
        self.assertEqual(item['mesa_proxima_colheita'], 'A2')
        self.assertEqual(item['proxima_colheita'], str(date.today() + timedelta(days=15)))

    def test_contagem_nao_multiplica_totais_de_colheita(self):
        colhido = self.lote(self.mesas[0], 60, status=CO)
        Colheita.objects.create(lote_id=colhido, funcionario_id=self.funcionario, quantidade_colhida=40,
                                quantidade_perda=10)
        self.lote(self.mesas[1], 5)
        self.lote(self.mesas[2], 3)
        item = self.item()
        self.assertEqual(item['lotes_ativos'], 2)
        self.assertEqual(item['total_colhido'], 40)
        self.assertEqual(item['total_perda'], 10)
        self.assertEqual(item['taxa_producao'], 80)

    def test_categoria_invalida(self):
        resposta = self.client.post(URL, {'nome_cultura': 'X', 'categoria': 'cacto', 'tempo_medio_colheita': 30,
                                          'temperatura_minima': 10, 'temperatura_maxima': 20, 'umidade_ideal': 60})
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('categoria', resposta.data)
