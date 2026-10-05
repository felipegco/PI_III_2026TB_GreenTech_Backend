from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from estufa.models import Estufa
from mesa.models import Mesa


class CapacidadeEstufaMesaTests(APITestCase):
    """Soma da capacidade das mesas não pode ultrapassar a capacidade da estufa."""

    def setUp(self):
        user = get_user_model().objects.create_user(username='tester', password='x')
        self.client.force_authenticate(user)
        self.estufa = Estufa.objects.create(
            nome_setor='Estufa A', tipo_cultivo='Hidroponia', capacidade_maxima=100
        )

    def _criar_mesa(self, identificacao, capacidade, estufa=None):
        return self.client.post('/api/mesa/', {
            'identificacao': identificacao,
            'estufa': (estufa or self.estufa).pk,
            'capacidade_maxima': capacidade,
        }, format='json')

    def test_cria_mesas_ate_o_limite(self):
        self.assertEqual(self._criar_mesa('M1', 60).status_code, 201)
        self.assertEqual(self._criar_mesa('M2', 40).status_code, 201)  # exatamente 100

    def test_bloqueia_mesa_que_ultrapassa_a_capacidade(self):
        self._criar_mesa('M1', 60)
        resp = self._criar_mesa('M2', 50)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('capacidade_maxima', resp.data)
        self.assertEqual(Mesa.objects.filter(estufa=self.estufa).count(), 1)

    def test_nao_aceita_infinitas_mesas(self):
        for i in range(4):
            self.assertEqual(self._criar_mesa(f'M{i}', 25).status_code, 201)
        self.assertEqual(self._criar_mesa('M-extra', 1).status_code, 400)

    def test_editar_mesa_desconsidera_ela_mesma(self):
        mesa_id = self._criar_mesa('M1', 60).data['id']
        resp = self.client.patch(f'/api/mesa/{mesa_id}/', {'capacidade_maxima': 100}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_editar_mesa_acima_do_limite_e_bloqueado(self):
        self._criar_mesa('M1', 60)
        mesa_id = self._criar_mesa('M2', 30).data['id']
        resp = self.client.patch(f'/api/mesa/{mesa_id}/', {'capacidade_maxima': 50}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_mover_mesa_para_estufa_sem_espaco_e_bloqueado(self):
        outra = Estufa.objects.create(nome_setor='Estufa B', tipo_cultivo='x', capacidade_maxima=30)
        mesa_id = self._criar_mesa('M1', 50).data['id']
        resp = self.client.patch(f'/api/mesa/{mesa_id}/', {'estufa': outra.pk}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_mesa_sem_estufa_nao_e_limitada(self):
        resp = self.client.post('/api/mesa/', {
            'identificacao': 'Avulsa', 'estufa': None, 'capacidade_maxima': 9999,
        }, format='json')
        self.assertEqual(resp.status_code, 201)

    def test_mesa_legada_acima_do_limite_pode_editar_outros_campos(self):
        mesa = Mesa.objects.create(
            estufa=self.estufa, identificacao='Antiga', capacidade_maxima=500
        )
        resp = self.client.patch(f'/api/mesa/{mesa.pk}/', {'observacoes': 'ok'}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_reduzir_estufa_abaixo_das_mesas_e_bloqueado(self):
        self._criar_mesa('M1', 70)
        resp = self.client.patch(f'/api/estufa/{self.estufa.pk}/', {'capacidade_maxima': 50}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('capacidade_maxima', resp.data)

    def test_reduzir_estufa_ate_o_total_alocado_e_permitido(self):
        self._criar_mesa('M1', 70)
        resp = self.client.patch(f'/api/estufa/{self.estufa.pk}/', {'capacidade_maxima': 70}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_estufa_expoe_capacidade_alocada_e_disponivel(self):
        self._criar_mesa('M1', 30)
        data = self.client.get(f'/api/estufa/{self.estufa.pk}/').data
        self.assertEqual(Decimal(str(data['capacidade_alocada'])), Decimal('30'))
        self.assertEqual(Decimal(str(data['capacidade_disponivel'])), Decimal('70'))
