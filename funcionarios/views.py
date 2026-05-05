from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Funcionario
from .serializers import FuncionarioSerializer, AlterarSenhaSerializer


class FuncionariosViewSet(viewsets.ModelViewSet):
    queryset = Funcionario.objects.all()
    serializer_class = FuncionarioSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get', 'patch', 'put'], url_path='me')
    def me(self, request):
        try:
            funcionario = Funcionario.objects.get(usuario=request.user)
        except Funcionario.DoesNotExist:
            return Response(
                {"detail": "Funcionário não encontrado para este usuário."},
                status=status.HTTP_404_NOT_FOUND
            )

        if request.method == 'GET':
            serializer = self.get_serializer(funcionario)
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif request.method in ['PATCH', 'PUT']:
            partial = request.method == 'PATCH'
            serializer = self.get_serializer(funcionario, data=request.data, partial=partial)

            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='me/alterar-senha')
    def alterar_senha(self, request):
        user = request.user
        serializer = AlterarSenhaSerializer(data=request.data)

        if serializer.is_valid():
            if not user.check_password(serializer.validated_data.get("senha_atual")):
                return Response(
                    {"senha_atual": "A senha atual está incorreta."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user.set_password(serializer.validated_data.get("nova_senha"))
            user.save()

            return Response({"message": "Senha alterada com sucesso!"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    def post(self, request):
        usuario = request.data.get('username')
        senha = request.data.get('password')

        user = authenticate(username=usuario, password=senha)

        if user is not None:
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "message": "Login com sucesso!",
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"erro": "Usuário ou senha inválidos."},
                status=status.HTTP_401_UNAUTHORIZED
            )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]

            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {"message": "Logout realizado com sucesso!"},
                status=status.HTTP_205_RESET_CONTENT
            )
        except Exception:
            return Response(
                {"error": "Token inválido ou já expirado."},
                status=status.HTTP_400_BAD_REQUEST
            )