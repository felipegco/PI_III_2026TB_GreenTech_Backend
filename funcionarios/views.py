from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.admin.models import LogEntry
import json

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


class AuditoriaGeralView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Barreira de Segurança
        if not user.is_superuser and not user.is_staff:
            return Response(
                {"error": "Acesso negado. Requer privilégios de auditoria."},
                status=status.HTTP_403_FORBIDDEN
            )

        logs = LogEntry.objects.all().select_related('content_type', 'user').order_by('-action_time')[:200]

        # 1. Dicionário para traduzir o nome das tabelas/módulos
        modulos_traduzidos = {
            'user': 'Usuário do Sistema',
            'group': 'Grupo de Acesso',
            'funcionario': 'Funcionário',
            'loteplantio': 'Lote de Plantio',
            'cultura': 'Cultura',
            'estoque': 'Estoque / Inventário',
            'mesa': 'Mesa de Cultivo',
            'estufa': 'Estufa',
            'colheita': 'Colheita',
        }

        dados_auditoria = []
        for log in logs:
            # Definindo a Ação
            if log.action_flag == 1:
                acao = "ADICIONOU"
            elif log.action_flag == 2:
                acao = "MODIFICOU"
            else:
                acao = "DELETOU"

            # Aplicando a tradução do módulo
            modelo_raw = log.content_type.model.lower() if log.content_type else "desconhecido"
            modulo_amigavel = modulos_traduzidos.get(modelo_raw, modelo_raw.upper())

            # 2. Parseando o JSON do Django Admin para um texto legível
            detalhes = log.change_message
            if detalhes:
                try:
                    parsed_msg = json.loads(detalhes)
                    if isinstance(parsed_msg, list):
                        mensagens_legiveis = []
                        for item in parsed_msg:
                            if 'added' in item:
                                mensagens_legiveis.append("Criou o registro inicial.")
                            elif 'changed' in item:
                                campos = item['changed'].get('fields', [])
                                if campos:
                                    campos_traduzidos = [c.capitalize() for c in campos]
                                    mensagens_legiveis.append(f"Alterou os campos: {', '.join(campos_traduzidos)}")
                                else:
                                    mensagens_legiveis.append("Modificou o registro.")
                            elif 'deleted' in item:
                                mensagens_legiveis.append("Excluiu o registro.")

                        # Junta as mensagens formatadas
                        detalhes = " | ".join(mensagens_legiveis) if mensagens_legiveis else detalhes
                except Exception:
                    # Se falhar ao ler como JSON, mantém o texto original
                    pass
            else:
                # Fallback caso não haja nenhuma mensagem
                if acao == "ADICIONOU":
                    detalhes = "Criou o registro inicial."
                elif acao == "DELETOU":
                    detalhes = "Excluiu o registro."
                else:
                    detalhes = "Alteração não detalhada."

            dados_auditoria.append({
                "id_log": log.id,
                "usuario": log.user.username if log.user else "Sistema",
                "acao": acao,
                "tabela_afetada": modulo_amigavel,
                "registro_afetado": log.object_repr,
                "detalhes": detalhes,
                "data_hora": log.action_time
            })

        return Response(dados_auditoria, status=status.HTTP_200_OK)