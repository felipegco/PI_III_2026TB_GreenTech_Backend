import json
import urllib.error
import urllib.request

from django.core.management.base import CommandError

# Prefixo das observações gravadas pelos simuladores, para ficar visível em qualquer tela que as exiba
PREFIXO_SIMULADO = '[SIMULADO]'


def enviar_para_api(endpoint, api_key, payload):
    """POST com a chave de API, como um microcontrolador faria. Devolve (status, corpo)."""
    requisicao = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Api-Key {api_key}'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=10) as resposta:
            return resposta.status, resposta.read().decode(errors='replace')
    except urllib.error.HTTPError as erro:
        return erro.code, erro.read().decode(errors='replace')
    except urllib.error.URLError as erro:
        raise CommandError(f'Não foi possível conectar em {endpoint}: {erro.reason}')
