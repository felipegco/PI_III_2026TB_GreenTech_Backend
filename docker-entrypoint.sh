#!/bin/sh
# Roda a cada vez que o container do backend sobe (inclusive pelo Start do Docker Desktop),
# depois que o serviço atualizar-repos já fez o git pull.
set -e

# Instala dependências novas só quando o requirements.txt mudou desde a última subida
HASH_ATUAL=$(sha256sum requirements.txt | cut -d' ' -f1)
HASH_SALVO=$(cat /tmp/requirements.sha 2>/dev/null || true)
if [ "$HASH_ATUAL" != "$HASH_SALVO" ]; then
    echo "→ requirements.txt mudou, instalando dependências..."
    pip install --no-cache-dir -q -r requirements.txt
    echo "$HASH_ATUAL" > /tmp/requirements.sha
fi

echo "→ Aplicando migrações..."
python manage.py migrate --noinput

exec python manage.py runserver 0.0.0.0:8000
