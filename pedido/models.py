from django.db import models
from estoque.models import ProdutoFinal
from django.utils import timezone
from cliente.models import Cliente


class Pedido(models.Model):
    class StatusPedido(models.TextChoices):
        PENDENTE = 'PE', 'Pendente'
        PAGO = 'PA', 'Pago'
        CANCELADO = 'CA', 'Cancelado'

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    data_pedido = models.DateTimeField(default=timezone.now)

    # ATENÇÃO AQUI: Adicione o .choices
    status_pedido = models.CharField(
        max_length=2,
        choices=StatusPedido.choices,
        default=StatusPedido.PENDENTE
    )
    valor_total_pedido = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Pedido #{self.id} - {self.cliente.nome}"

    class Meta:
        db_table = 'pedido'


class PedidoItem(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    produto_final = models.ForeignKey(ProdutoFinal, on_delete=models.CASCADE)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Item {self.produto_final.nome_produto} (Pedido #{self.pedido.id})"

    class Meta:
        db_table = 'pedido_item'