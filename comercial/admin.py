from django.contrib import admin
from .models import Cliente, Pedido, PedidoItem

admin.site.register(Cliente)
admin.site.register(Pedido)
admin.site.register(PedidoItem)