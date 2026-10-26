from datetime import date

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from colheita.models import Colheita
from cultura.models import Cultura
from estoque.models import Estoque
from estufa.models import Estufa
from funcionarios.models import Funcionario
from lotePlantio.models import LotePlantio
from mesa.models import Mesa

URL_LOTES = '/api/lotes/'


class BaseLoteTests(APITestCase):

    def setUp(self):
        Funcionario.objects.create(nome_completo='Primeiro Cadastrado', cpf='000.000.000-00')
        usuario = get_user_model().objects.create_user(username='operador', password='x')
        self.funcionario = Funcionario.objects.create(nome_completo='Operador', cpf='111.111.111-11', usuario=usuario)
        self.client.force_authenticate(usuario)
        estufa = Estufa.objects.create(nome_setor='Estufa A', tipo_cultivo='NFT', capacidade_maxima=300)
        self.mesa = Mesa.objects.create(estufa=estufa, identificacao='A1', capacidade_maxima=100)
        self.alface = Cultura.objects.create(nome_cultura='Alface', tempo_medio_colheita=45,
                                             temperatura_minima=15, temperatura_maxima=24, umidade_ideal=70)

    def plantar(self, **extra):
        dados = {'cultura_id': self.alface.pk, 'mesa_id': self.mesa.pk, 'data_plantio': str(date.today()),
                 'quantidade': 80, 'unidade': 'UN', **extra}
        return self.client.post(URL_LOTES, dados, format='json')


class PlantioTests(BaseLoteTests):

    def test_plantio_sempre_comeca_em_cultivo_e_registra_entrada_de_quem_plantou(self):
        resp = self.plantar(status='ES')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['status'], 'AT')
        entrada = Estoque.objects.get()
        self.assertEqual((entrada.tipo_movimentacao, entrada.funcionario_id), ('Entrada', self.funcionario))

    def test_mesa_fica_ocupada_e_nao_aceita_segundo_plantio(self):
        self.plantar()
        self.assertEqual(self.client.get(f'/api/mesa/{self.mesa.pk}/').data['status_mesa'], 'ocupada')
        resp = self.plantar()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('já tem o lote', str(resp.data['mesa_id']))

    def test_plantio_respeita_capacidade_manutencao_e_mesa_sem_estufa(self):
        self.assertEqual(self.plantar(quantidade=150).status_code, 400)
        self.mesa.status_mesa = Mesa.Status.MANUTENCAO
        self.mesa.save()
        self.assertEqual(self.plantar().status_code, 400)
        avulsa = Mesa.objects.create(estufa=None, identificacao='NF-AUTO')
        self.assertEqual(self.plantar(mesa_id=avulsa.pk).status_code, 400)

    def test_nao_planta_cultura_com_cadastro_incompleto(self):
        incompleta = Cultura.objects.create(nome_cultura='Item da NF', tempo_medio_colheita=0,
                                            temperatura_minima=0, temperatura_maxima=0, umidade_ideal=0)
        resp = self.plantar(cultura_id=incompleta.pk)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Complete o cadastro', str(resp.data['cultura_id']))

    def test_status_e_saldo_nao_mudam_por_edicao_direta(self):
        lote_id = self.plantar().data['id']
        self.client.patch(f'{URL_LOTES}{lote_id}/', {'status': 'CO'}, format='json')
        self.assertEqual(LotePlantio.objects.get().status, 'AT')
        self.assertEqual(self.client.patch(f'{URL_LOTES}{lote_id}/', {'quantidade': 5}, format='json').status_code, 400)

    def test_mesa_com_plantio_nao_entra_em_manutencao(self):
        self.plantar()
        resp = self.client.patch(f'/api/mesa/{self.mesa.pk}/', {'status_mesa': 'manutencao'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.client.patch(f'/api/mesa/{self.mesa.pk}/', {'status_mesa': 'ocupada'},
                                           format='json').status_code, 400)


class PerdaTests(BaseLoteTests):

    def test_perda_parcial_mantem_o_lote_e_perda_total_encerra(self):
        lote_id = self.plantar().data['id']
        url = f'{URL_LOTES}{lote_id}/registrar_perda/'
        resp = self.client.post(url, {'quantidade': 30, 'motivo': 'Pulgão'}, format='json')
        self.assertEqual((resp.status_code, resp.data['status'], resp.data['quantidade']), (200, 'AT', 50))
        resp = self.client.post(url, {'motivo': 'Lote condenado'}, format='json')
        self.assertEqual((resp.data['status'], resp.data['quantidade']), ('PE', 0))
        self.assertEqual(Estoque.objects.filter(tipo_movimentacao='Perda').count(), 2)
        # Mesa liberada para novo plantio
        self.assertEqual(self.plantar().status_code, 201)

    def test_perda_exige_motivo_e_saldo(self):
        lote_id = self.plantar().data['id']
        url = f'{URL_LOTES}{lote_id}/registrar_perda/'
        self.assertEqual(self.client.post(url, {'quantidade': 10}, format='json').status_code, 400)
        self.assertEqual(self.client.post(url, {'quantidade': 81, 'motivo': 'x'}, format='json').status_code, 400)


class ColheitaTests(BaseLoteTests):

    def colher(self, lote_id, colhido, perda=0):
        return self.client.post('/api/colheita/', {'lote_id': lote_id, 'quantidade_colhida': colhido,
                                                   'quantidade_perda': perda}, format='json')

    def test_colheita_encerra_lote_e_registra_sobra_como_perda(self):
        lote_id = self.plantar().data['id']
        self.assertEqual(self.colher(lote_id, 70, 4).status_code, 201)
        lote = LotePlantio.objects.get()
        self.assertEqual((lote.status, lote.quantidade), ('CO', 0))
        baixas = {(m.tipo_movimentacao, m.quantidade) for m in Estoque.objects.exclude(tipo_movimentacao='Entrada')}
        self.assertEqual(baixas, {('Saída', 70), ('Perda', 4), ('Perda', 6)})
        colheita = Colheita.objects.get()
        self.assertEqual((colheita.funcionario_id, colheita.quantidade_perda), (self.funcionario, 10))
        self.assertEqual(self.client.get(f'/api/mesa/{self.mesa.pk}/').data['status_mesa'], 'livre')

    def test_colheita_recusa_lote_encerrado_ou_acima_do_saldo(self):
        lote_id = self.plantar().data['id']
        self.assertEqual(self.colher(lote_id, 79, 2).status_code, 400)
        self.assertEqual(self.colher(lote_id, 0).status_code, 400)
        self.colher(lote_id, 80)
        self.assertEqual(self.colher(lote_id, 1).status_code, 400)
        self.assertEqual(Colheita.objects.count(), 1)

    def test_lote_encerrado_nao_recebe_movimentacao_de_estoque(self):
        lote_id = self.plantar().data['id']
        self.colher(lote_id, 80)
        resp = self.client.post('/api/estoque/', {'lote_id': lote_id, 'tipo_movimentacao': 'Entrada',
                                                  'quantidade': 5, 'unidade': 'UN'}, format='json')
        self.assertEqual(resp.status_code, 400)


class CulturaTests(BaseLoteTests):

    def test_cultura_valida_faixa_e_ciclo(self):
        base = {'nome_cultura': 'Rúcula', 'tempo_medio_colheita': 35, 'temperatura_minima': 25,
                'temperatura_maxima': 15, 'umidade_ideal': 70}
        self.assertEqual(self.client.post('/api/cultura/', base, format='json').status_code, 400)
        base.update(temperatura_minima=15, temperatura_maxima=25, tempo_medio_colheita=0)
        self.assertEqual(self.client.post('/api/cultura/', base, format='json').status_code, 400)


class TransplanteTests(BaseLoteTests):

    def setUp(self):
        super().setUp()
        bercario = Mesa.objects.create(estufa=self.mesa.estufa, identificacao='C2', capacidade_maxima=50)
        self.mudas = LotePlantio.objects.create(cultura_id=self.alface, mesa_id=bercario, data_plantio=date.today(),
                                                status='ES', quantidade=6, unidade='BD')

    def test_transplante_baixa_as_mudas_do_estoque(self):
        resp = self.plantar(lote_origem=self.mudas.pk, quantidade_origem=4)
        self.assertEqual(resp.status_code, 201)
        self.mudas.refresh_from_db()
        self.assertEqual((self.mudas.quantidade, self.mudas.status), (2, 'ES'))
        self.assertEqual(resp.data['fornecedor'], f'Transplante do lote #{self.mudas.pk} (C2)')
        saida = Estoque.objects.get(lote_id=self.mudas)
        self.assertEqual((saida.tipo_movimentacao, saida.quantidade), ('Saída', 4))

    def test_usar_todas_as_mudas_marca_estoque_baixo(self):
        self.plantar(lote_origem=self.mudas.pk, quantidade_origem=6)
        self.mudas.refresh_from_db()
        self.assertEqual((self.mudas.quantidade, self.mudas.status), (0, 'BX'))

    def test_transplante_valida_saldo_cultura_e_quantidade(self):
        self.assertEqual(self.plantar(lote_origem=self.mudas.pk, quantidade_origem=7).status_code, 400)
        self.assertEqual(self.plantar(lote_origem=self.mudas.pk).status_code, 400)
        rucula = Cultura.objects.create(nome_cultura='Rúcula', tempo_medio_colheita=35,
                                        temperatura_minima=15, temperatura_maxima=25, umidade_ideal=70)
        self.assertEqual(self.plantar(cultura_id=rucula.pk, lote_origem=self.mudas.pk,
                                      quantidade_origem=1).status_code, 400)
        self.assertFalse(LotePlantio.objects.filter(status='AT').exists())


class ExclusaoTests(BaseLoteTests):

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(get_user_model().objects.create_superuser(username='admin', password='x'))

    def test_so_exclui_lote_sem_historico(self):
        lote_id = self.plantar().data['id']
        self.client.post('/api/colheita/', {'lote_id': lote_id, 'quantidade_colhida': 80}, format='json')
        self.assertEqual(self.client.delete(f'{URL_LOTES}{lote_id}/').status_code, 400)
        novo = self.plantar().data['id']
        self.assertEqual(self.client.delete(f'{URL_LOTES}{novo}/').status_code, 204)

    def test_cultura_com_lotes_nao_e_excluida(self):
        self.plantar()
        self.assertEqual(self.client.delete(f'/api/cultura/{self.alface.pk}/').status_code, 400)
        vazia = Cultura.objects.create(nome_cultura='Teste', tempo_medio_colheita=10,
                                       temperatura_minima=10, temperatura_maxima=20, umidade_ideal=60)
        self.assertEqual(self.client.delete(f'/api/cultura/{vazia.pk}/').status_code, 204)
