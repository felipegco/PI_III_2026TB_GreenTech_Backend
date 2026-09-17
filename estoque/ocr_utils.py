"""
Extração "OCR" simples de notas fiscais.

Este módulo NÃO usa um motor de OCR real (Tesseract, etc). Ele:

1. Extrai o texto embutido de arquivos PDF (funciona bem para notas fiscais
   eletrônicas em PDF, que já têm o texto na camada digital do arquivo).
2. Aplica um conjunto de expressões regulares heurísticas sobre esse texto
   para tentar identificar número da nota, data de emissão, fornecedor e a
   lista de itens (descrição, quantidade, unidade e valor).

Limitações conhecidas (documentadas de propósito, para evoluir depois):
- Imagens (jpg/png) e PDFs escaneados (sem camada de texto) NÃO são
  suportados nesta versão: não há OCR de imagem real. Nesses casos a
  extração retorna texto vazio e a view devolve um erro amigável.
- As regras de regex foram desenhadas para o formato "genérico" de notas
  fiscais brasileiras (DANFE). Notas com layout muito diferente podem exigir
  ajuste nas expressões abaixo.

Para evoluir no futuro: trocar `extrair_texto_arquivo` por uma implementação
que rode Tesseract/pdf2image sobre imagens e PDFs escaneados, mantendo a
mesma interface (recebe um arquivo, devolve uma string de texto).
"""

import io
import re
from datetime import datetime

from pypdf import PdfReader


class NotaFiscalOcrError(Exception):
    """Erro esperado (arquivo inválido / sem texto extraível)."""


UNIDADES_CONHECIDAS = (
    "kg", "g", "l", "ml", "un", "und", "unid", "unidade",
    "cx", "caixa", "pct", "pacote", "sc", "saco", "dz", "duzia", "dúzia",
)


def extrair_texto_arquivo(arquivo) -> str:
    """
    Recebe um arquivo do request (InMemoryUploadedFile) e devolve o texto
    extraível dele. Só sabemos extrair texto de PDFs com camada de texto.
    """
    nome = (arquivo.name or "").lower()

    if not nome.endswith(".pdf"):
        # Imagem (jpg/png/etc) ou outro formato: sem OCR real, não há texto.
        raise NotaFiscalOcrError(
            "No momento só é possível extrair dados automaticamente de notas "
            "fiscais em PDF (com texto selecionável). Suporte a imagens "
            "escaneadas (OCR de imagem) ainda não foi implementado."
        )

    try:
        conteudo = arquivo.read()
        leitor = PdfReader(io.BytesIO(conteudo))
        texto = "\n".join((pagina.extract_text() or "") for pagina in leitor.pages)
    except Exception as exc:
        raise NotaFiscalOcrError(f"Não foi possível ler o PDF enviado: {exc}")

    texto = texto.strip()
    if not texto:
        raise NotaFiscalOcrError(
            "O PDF enviado não possui texto extraível (provavelmente é uma "
            "digitalização/escaneamento). Suporte a OCR de imagem ainda não "
            "foi implementado."
        )

    return texto


def _extrair_numero(texto: str) -> str | None:
    padroes = [
        r"N[º°o]\.?\s*(?:da\s*)?(?:NF-?e?|Nota\s*Fiscal)?\s*[:\-]?\s*([\d.\-]{3,20})",
        r"N[uú]mero\s*[:\-]?\s*([\d.\-]{3,20})",
        r"NF-?e?\s*n?[º°o]?\s*[:\-]?\s*([\d.\-]{3,20})",
    ]
    for padrao in padroes:
        m = re.search(padrao, texto, re.IGNORECASE)
        if m:
            return m.group(1).strip(" .-")
    return None


def _extrair_data_emissao(texto: str) -> str | None:
    m = re.search(
        r"(?:Data\s*(?:de\s*)?Emiss[ãa]o|Emitida\s*em)\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
        texto, re.IGNORECASE,
    )
    if not m:
        # fallback: primeira data no formato dd/mm/aaaa encontrada no texto
        m = re.search(r"(\d{2}/\d{2}/\d{4})", texto)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def _extrair_fornecedor(texto: str) -> str | None:
    # 1) rótulo explícito e inequívoco de quem EMITIU a nota (o fornecedor,
    # do ponto de vista de quem está recebendo a mercadoria).
    m = re.search(r"(?:Fornecedor|Emitente)\s*[:\-]?\s*([^\n]{3,150})", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # 2) Numa DANFE, "RAZÃO SOCIAL" aparece tanto para o emitente quanto para
    # o destinatário/remetente — sem cuidado, isso pega o nome do CLIENTE
    # (vocês mesmos) em vez do fornecedor. Por isso: pegamos só o texto ANTES
    # da seção "DESTINATÁRIO/REMETENTE", que é o cabeçalho do documento (onde
    # fica o nome de quem emitiu a nota).
    cabecalho = re.split(r"DESTINAT[ÁA]RIO|REMETENTE", texto, maxsplit=1, flags=re.IGNORECASE)[0]

    m = re.search(r"(?:Raz[ãa]o\s*Social)\s*[:\-]?\s*([^\n]{3,150})", cabecalho, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # 3) fallback: primeira linha "útil" do cabeçalho (pula linhas que
    # claramente são endereço/CNPJ/telefone), que costuma ser o nome da
    # empresa emissora.
    for linha in cabecalho.splitlines():
        linha = linha.strip()
        if len(linha) < 4:
            continue
        if re.match(r"^(rua|av\.|avenida|cnpj|ie[:\s]|fone|tel\b)", linha, re.IGNORECASE):
            continue
        return linha
    return None


UNIDADES_TOKEN = r"[A-Za-zÀ-ÿ]{1,6}"

# Item no formato de tabela de uma DANFE real, onde cada campo pode ter saído
# em uma linha separada na extração de texto do PDF (por isso comparamos
# sobre o texto "achatado", com todo espaço em branco/quebra de linha
# convertido em um único espaço). Colunas: código, descrição, NCM, CFOP,
# unidade, quantidade, valor unitário, valor total, valor ICMS, %ICMS.
PADRAO_ITEM_DANFE = re.compile(
    r"\b\d{1,8}\s+"
    r"(?P<descricao>[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9\s.,\-/]{1,60}?)\s+"
    r"\d{4}\.\d{2}\.\d{2}\s+"          # NCM, ex: 8471.30.12
    r"\d{2,4}\s+"                       # CFOP, ex: 5102
    r"(?P<unidade>" + UNIDADES_TOKEN + r")\s+"
    r"(?P<quantidade>\d+(?:[.,]\d+)?)\s+"
    r"(?P<vunit>\d+(?:[.,]\d+)?)\s+"
    r"(?P<vtotal>\d+(?:[.,]\d+)?)\s+"
    r"\d+(?:[.,]\d+)?\s+"               # valor do ICMS
    r"\d+(?:[.,]\d+)?%",                # % ICMS
)

# Item em formato "simples", uma linha só: "<descrição> <quantidade> <unidade> ... <valor>"
# Ex.: "Nitrato de Cálcio   50   kg   450,00"
UNIDADES_CONHECIDAS_REGEX = "|".join(UNIDADES_CONHECIDAS)
PADRAO_ITEM_SIMPLES = re.compile(
    r"^(?P<descricao>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-]{2,60}?)\s+"
    r"(?P<quantidade>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unidade>" + UNIDADES_CONHECIDAS_REGEX + r")\b"
    r"[^\d]{0,15}"
    r"(?P<valor>\d+[.,]\d{2})?",
    re.IGNORECASE,
)


def _para_float(valor: str) -> float:
    """Converte '1.234,56' ou '1234,56' ou '1234.56' para float."""
    valor = valor.strip()
    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    return float(valor)


def _extrair_itens_danfe(texto: str) -> list[dict]:
    """Tenta casar o formato de tabela completo de uma DANFE (com colunas de
    NCM e CFOP), rodando sobre o texto com espaços/quebras de linha
    normalizados — assim funciona tanto se o PDF extraiu cada célula da
    tabela numa linha separada quanto se extraiu tudo na mesma linha.

    Importante: restringimos a busca à seção "DADOS DOS PRODUTOS/SERVIÇOS"
    da nota. Sem isso, o regex pode "vazar" e casar números/textos de outras
    seções do documento (CNPJ, chave de acesso, etc.) como se fossem um item.
    """
    texto_achatado = re.sub(r"\s+", " ", texto)

    secao = re.search(
        r"DADOS\s+DOS\s+PRODUTOS.*?(?=DADOS\s+ADICIONAIS|C[ÁA]LCULO\s+DO\s+ISSQN|$)",
        texto_achatado, re.IGNORECASE,
    )
    texto_secao = secao.group(0) if secao else texto_achatado

    itens = []
    for m in PADRAO_ITEM_DANFE.finditer(texto_secao):
        itens.append({
            "descricao": m.group("descricao").strip(" .-"),
            "quantidade": _para_float(m.group("quantidade")),
            "unidade": m.group("unidade").lower(),
            "valor": _para_float(m.group("vtotal")),
        })
    return itens


def _extrair_itens_simples(texto: str) -> list[dict]:
    """Formato mais simples, sem colunas de NCM/CFOP: uma linha por item."""
    itens = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        m = PADRAO_ITEM_SIMPLES.match(linha)
        if not m:
            continue

        valor_bruto = m.group("valor")
        itens.append({
            "descricao": m.group("descricao").strip(),
            "quantidade": _para_float(m.group("quantidade")),
            "unidade": m.group("unidade").lower(),
            "valor": _para_float(valor_bruto) if valor_bruto else None,
        })
    return itens


def _extrair_itens(texto: str) -> list[dict]:
    """Tenta primeiro o formato completo de DANFE (mais específico e mais
    comum em notas reais); se não achar nada, cai para o formato simples."""
    return _extrair_itens_danfe(texto) or _extrair_itens_simples(texto)


def extrair_dados_nota(texto: str) -> dict:
    """Aplica as heurísticas de regex e devolve o dicionário no formato
    esperado pelo frontend: { numero, dataEmissao, fornecedor, itens }.
    """
    itens = _extrair_itens(texto)

    if not itens:
        raise NotaFiscalOcrError(
            "Não foi possível identificar os itens da nota fiscal a partir "
            "do texto extraído. Verifique o arquivo ou ajuste manualmente "
            "os dados antes de confirmar a entrada em estoque."
        )

    return {
        "numero": _extrair_numero(texto),
        "dataEmissao": _extrair_data_emissao(texto),
        "fornecedor": _extrair_fornecedor(texto),
        "itens": itens,
    }