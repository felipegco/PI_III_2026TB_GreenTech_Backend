# GrennTech — API Backend

API RESTful desenvolvida para o sistema de gestão agrícola **GrennTech**, responsável por gerenciar estufas, lotes de plantio, estoques, funcionários, clientes e pedidos.

---

## Tecnologias Utilizadas

| Tecnologia | Uso |
|---|---|
| Python 3.x | Linguagem principal |
| Django | Framework web |
| Django REST Framework | Construção da API REST |
| PostgreSQL | Banco de dados relacional |
| python-dotenv | Gerenciamento de variáveis de ambiente |

---

## Arquitetura de Módulos

O projeto é dividido em **apps independentes** para garantir escalabilidade e separação de responsabilidades:

| App | Responsabilidade |
|---|---|
| `cliente` | Gestão de clientes |
| `estoque` | Insumos e produtos finais |
| `estufa` | Cadastro e monitoramento das estufas |
| `funcionarios` | Equipe, integrado ao `User` do Django |
| `producao` | Lotes de plantio, manejos e colheitas |
| `pedido` | Controle comercial e de vendas |
| `registroClima` | Monitoramento de temperatura e umidade |

---

## Executando o Projeto Localmente

### Pré-requisitos

- Python 3.x
- PostgreSQL instalado e em execução
- Git

### 1. Clonar o repositório

```bash
git clone https://github.com/SEU_USUARIO/GrennTech-backend.git
cd GrennTech-backend
```

### 2. Criar e ativar o ambiente virtual

```bash
# Criar
python -m venv .venv

# Ativar no macOS/Linux
source .venv/bin/activate

# Ativar no Windows
.venv\Scripts\activate
```

### 3. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto (mesma pasta do `manage.py`) com o seguinte conteúdo:

```ini
SECRET_KEY=sua_chave_secreta_do_django_aqui
```

> **Atenção:** nunca versione o arquivo `.env`. Certifique-se de que ele está no `.gitignore`.

### 5. Criar o banco de dados

No PostgreSQL, execute:

```sql
CREATE DATABASE greentech_db;
```

### 6. Executar as migrações

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Criar um superusuário

```bash
python manage.py createsuperuser
```

### 8. Iniciar o servidor

```bash
python manage.py runserver
```

A API estará disponível em: **`http://127.0.0.1:8000/api/`**

O painel administrativo estará em: **`http://127.0.0.1:8000/admin/`**

---

## Endpoints da API

Todos os endpoints seguem o padrão REST e suportam os seguintes métodos:

| Método | Ação |
|---|---|
| `GET /recurso/` | Lista todos os registros |
| `POST /recurso/` | Cria um novo registro |
| `GET /recurso/{id}/` | Retorna um registro específico |
| `PUT /recurso/{id}/` | Atualiza um registro completo |
| `PATCH /recurso/{id}/` | Atualiza campos específicos |
| `DELETE /recurso/{id}/` | Remove um registro |

### Clientes

```
/api/clientes/
```

### Estoque

```
/api/estoque/insumos/     # Adubos, sementes, etc.
/api/estoque/produtos/    # Produtos prontos para venda
```

### Estufas e Clima

```
/api/estufas/
/api/clima/               # Registros de temperatura e umidade
```

### Produção

```
/api/lotes/
/api/manejos/
/api/colheita/
```

### Comercial e Equipe

```
/api/pedidos/
/api/funcionarios/
```

---

## Estrutura do Projeto

```
GrennTech-backend/
├── cliente/
├── estoque/
├── estufa/
├── funcionarios/
├── producao/
├── pedido/
├── registroClima/
├── manage.py
├── requirements.txt
└── .env               # Não versionado
```
