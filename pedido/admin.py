from django.contrib import admin
from pedido.models import Pedido, PedidoItem

admin.site.register(Pedido)
admin.site.register(PedidoItem)