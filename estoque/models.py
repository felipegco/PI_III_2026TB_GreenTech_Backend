from django.db import models

class Insumo(models.Model):
    nome_insumo = models.CharField(max_length=100)
    categoria = models.CharField(max_length=50)
    unidade_medida = models.CharField(max_length=20)
    quantidade_estoque = models.IntegerField()
    custo_unitario = models.FloatField()

    class Meta:
        db_table = 'insumo'

    def __str__(self):
        return self.nome_insumo

class ProdutoFinal(models.Model):
    nome_produto = models.CharField(max_length=100)
    classificacao = models.CharField(max_length=50)
    preco_venda = models.FloatField()
    quantidade_estoque = models.IntegerField(default=0)

    class Meta:
        db_table = 'produto_final'

    def __str__(self):
        return self.nome_produto