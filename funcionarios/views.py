from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from .models import Funcionario
from .serializers import FuncionarioSerializer


class FuncionariosViewSet(viewsets.ModelViewSet):
    queryset = Funcionario.objects.all()
    serializer_class = FuncionarioSerializer


class LoginView(APIView):
    def post(self, request):
        usuario = request.data.get('username')
        senha = request.data.get('password')

        # verifica automaticamente se o usuário e senha existem no banco
        user = authenticate(username=usuario, password=senha)

        if user is not None:
            return Response({"message": "Login com sucesso!"}, status=status.HTTP_200_OK)
        else:
            return Response({"erro": "Usuário ou senha inválidos."}, status=status.HTTP_401_UNAUTHORIZED)