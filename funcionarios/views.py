from rest_framework import viewsets
from estufa.models import Estufa
from funcionarios.serializers import FuncionarioSerializer

class FuncionariosViewSet(viewsets.ModelViewSet):
    queryset = Estufa.objects.all()
    serializer_class = FuncionarioSerializer