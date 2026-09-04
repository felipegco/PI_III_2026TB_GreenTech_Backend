# GreenTech — API Backend

API RESTful desenvolvida para o sistema de gestão agrícola **GreenTech ERP**, responsável por gerenciar estufas, culturas, lotes de plantio, colheitas, estoque, mesas de cultivo, registros climáticos/irrigação e funcionários (com controle de acesso por cargo).

---

## Tecnologias Utilizadas

| Tecnologia | Versão | Uso |
|---|---|---|
| Python | 3.12+ | Linguagem principal |
| Django | 4.2.11 | Framework web |
| Django REST Framework | 3.15.2 | Construção da API REST |
| djangorestframework-simplejwt | 5.5.1 | Autenticação via JWT |
| django-cors-headers | 4.9.0 | Liberação de CORS para o frontend |
| PostgreSQL | 16 | Banco de dados relacional |
| psycopg2-binary | 2.9.11 | Driver de conexão com o PostgreSQL |
| python-dotenv | 1.2.1 | Gerenciamento de variáveis de ambiente |
| Docker / Docker Compose | — | Orquestração do ambiente completo (API + banco + frontend) |

---

## Arquitetura de Módulos (Apps Django)

| App | Responsabilidade |
|---|---|
| `funcionarios` | Equipe, integrado ao `User` do Django; login/JWT; controle de acesso por Grupo (cargo); auditoria geral |
| `cultura` | Catálogo de espécies cultivadas (ciclo, temperatura ideal, umidade ideal) |
| `lotePlantio` | Lotes de plantio: alocação, mesa de destino, status, maturação |
| `mesa` | Mesas/bancadas de cultivo dentro das estufas |
| `estufa` | Cadastro das estufas |
| `colheita` | Registro de colheitas (baixa de lote, aproveitamento vs. perda) |
| `estoque` | Movimentações de estoque (entrada/saída/perda/ajuste) por lote |
| `registroClima` | Leituras de sensores climáticos e registros de irrigação |
| `authentication` | App reservado para expansões futuras de autenticação (atualmente sem lógica própria) |

### Sistema de Cargos (Grupos do Django)

O controle de permissão **não** usa um campo `cargo` no model `Funcionario` — ele é resolvido via **Grupos nativos do Django** (`django.contrib.auth.models.Group`), atribuídos a cada `User`. Os quatro cargos padrão são criados automaticamente na primeira execução das migrations (`funcionarios/migrations/0004_criar_cargos_padrao.py`):

| Grupo | Uso |
|---|---|
| `admin` | Acesso administrativo total |
| `gerente` | Gestão operacional, acesso à auditoria e exclusões |
| `operador` | Operação do dia a dia |
| `tecnico` | Suporte técnico |

Para atribuir um cargo a um funcionário: crie o `User` em **Django Admin → Users**, salve, e na mesma tela de edição use o campo **Groups** para marcar o grupo desejado (ou, se preferir, edite via **Funcionarios → Grupo de Acesso** no admin customizado).

---

## Executando com Docker (recomendado)

Este é o jeito mais rápido de subir **backend + PostgreSQL + frontend** juntos, sem precisar instalar Python, PostgreSQL ou Node localmente.

### Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e **em execução**
- Ter clonado também o repositório do frontend em algum lugar do seu computador: [PI_III_2026TB_GreenTech_FrontEnd](https://github.com/LKSS17/PI_III_2026TB_GreenTech_FrontEnd)

### 1. Clonar os repositórios

```bash
git clone https://github.com/felipegco/PI_III_2026TB_GreenTech_Backend.git
git clone https://github.com/LKSS17/PI_III_2026TB_GreenTech_FrontEnd.git
```

*(Podem ficar em pastas completamente separadas no seu computador — o caminho do frontend é configurável no passo 3.)*

### 2. Entrar na pasta do Docker

```bash
cd PI_III_2026TB_GreenTech_Backend/docker-greentech
```

### 3. Configurar o caminho do frontend

Copie o arquivo de exemplo e edite com o caminho **absoluto** de onde você clonou o frontend:

```bash
cp .env.example .env
```

Edite o `.env` gerado:

```env
FRONTEND_PATH=/caminho/completo/para/PI_III_2026TB_GreenTech_FrontEnd
```

> O Docker Compose lê esse `.env` automaticamente, por estar na mesma pasta do `docker-compose.yml` — não é preciso passar nenhuma flag extra.

### 4. Subir tudo

```bash
docker compose up --build
```

Isso sobe três containers:

| Serviço | O que é | Porta no host |
|---|---|---|
| `db` | PostgreSQL 16 | `5432` |
| `backend` | Django (aplica migrations automaticamente e roda o servidor) | `8000` |
| `frontend` | Vite dev server (Vue 3) | `5173` |

Acesse:
- **Frontend:** http://localhost:5173/
- **API:** http://localhost:8000/api/
- **Admin do Django:** http://localhost:8000/admin/

### 5. Criar o superusuário (só na primeira vez)

Com os containers de pé, em outro terminal:

```bash
docker compose exec backend python manage.py createsuperuser
```

### Comandos úteis do dia a dia

```bash
docker compose up -d --build     # sobe em segundo plano
docker compose logs -f backend   # acompanha logs do backend
docker compose logs -f frontend  # acompanha logs do frontend
docker compose down              # derruba os containers (mantém os dados do banco)
docker compose down -v           # derruba TUDO, incluindo o volume do Postgres (apaga os dados)
```

> **Hot reload:** tanto o backend quanto o frontend rodam com bind mount do código-fonte — qualquer alteração salva localmente reflete direto nos containers, sem precisar rebuildar (exceto quando você altera `requirements.txt` ou `package.json`, aí é necessário `docker compose up --build` de novo).

---

## Executando Localmente (sem Docker)

### Pré-requisitos

- Python 3.12+
- PostgreSQL instalado e em execução
- Git

### 1. Clonar o repositório

```bash
git clone https://github.com/felipegco/PI_III_2026TB_GreenTech_Backend.git
cd PI_III_2026TB_GreenTech_Backend
```

### 2. Criar e ativar o ambiente virtual

```bash
python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto (mesma pasta do `manage.py`):

```env
SECRET_KEY=sua_chave_secreta_do_django_aqui
POSTGRES_DB=greentech_db
POSTGRES_USER=greentech
POSTGRES_PASSWORD=sua_senha_local
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
```

> **Nunca versione o `.env`** — confirme que ele está no `.gitignore`.

### 5. Criar o banco de dados

```sql
CREATE DATABASE greentech_db;
```

### 6. Rodar as migrações

```bash
python manage.py migrate
```

*(Isso já cria os cargos padrão automaticamente — ver seção "Sistema de Cargos" acima.)*

### 7. Criar um superusuário

```bash
python manage.py createsuperuser
```

### 8. Iniciar o servidor

```bash
python manage.py runserver
```

A API estará disponível em **http://127.0.0.1:8000/api/** e o admin em **http://127.0.0.1:8000/admin/**.

---

## Endpoints da API

Todos os recursos abaixo (exceto autenticação) seguem o padrão REST do Django REST Framework:

| Método | Ação |
|---|---|
| `GET /recurso/` | Lista todos os registros |
| `POST /recurso/` | Cria um novo registro |
| `GET /recurso/{id}/` | Retorna um registro específico |
| `PUT /recurso/{id}/` | Atualiza um registro completo |
| `PATCH /recurso/{id}/` | Atualiza campos específicos |
| `DELETE /recurso/{id}/` | Remove um registro |

### Autenticação (JWT)

```
POST /api/token/            # login — retorna access + refresh token
POST /api/token/refresh/    # renova o access token
POST /api/logout/           # invalida o refresh token (blacklist)
```

### Funcionários & Auditoria

```
/api/funcionarios/                    # CRUD de funcionários
/api/funcionarios/me/                 # dados do funcionário autenticado (GET/PATCH/PUT)
/api/funcionarios/me/alterar-senha/   # troca de senha (POST)
/api/funcionarios/auditoria/          # log de auditoria geral (GET, restrito a gerente/admin)
```

### Culturas, Lotes e Estrutura Física

```
/api/cultura/     # catálogo de espécies
/api/lotes/       # lotes de plantio
/api/mesa/        # mesas de cultivo
/api/estufa/      # estufas
```

### Colheita e Estoque

```
/api/colheita/    # registro de colheitas
/api/estoque/     # movimentações de estoque
```

### Clima e Irrigação

```
/api/clima/       # leituras de sensores climáticos
/api/irrigacao/   # registros/controle de irrigação
```

---

## Estrutura do Projeto

```
PI_III_2026TB_GreenTech_Backend/
├── authentication/
├── colheita/
├── cultura/
├── docker-greentech/
│   ├── docker-compose.yml
│   ├── .env.example        # versionado (template)
│   └── .env                # não versionado (caminho real do frontend)
├── Dockerfile
├── estoque/
├── estufa/
├── funcionarios/
├── GrennTech_backend/       # configurações do projeto Django (settings, urls, wsgi)
├── lotePlantio/
├── manage.py
├── mesa/
├── registroClima/
├── requirements.txt
└── .env                     # não versionado (variáveis locais/Docker do Django)
```

---

## Frontend

O frontend (Vue 3 + Vite) vive em um repositório separado:
[PI_III_2026TB_GreenTech_FrontEnd](https://github.com/LKSS17/PI_III_2026TB_GreenTech_FrontEnd)

Ao usar Docker (ver seção acima), ele já sobe junto automaticamente — não é necessário clonar/rodar `npm install` manualmente.
