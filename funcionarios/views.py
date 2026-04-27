from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

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


class LogoutView(APIView):
    # Só deixa deslogar se estiver logado
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # Pega o refresh token que o Front-end enviou no POST
            refresh_token = request.data["refresh"]

            # Instancia o token e manda para a lista negra
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response({"message": "Logout realizado com sucesso!"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": "Token inválido ou já expirado."}, status=status.HTTP_400_BAD_REQUEST)