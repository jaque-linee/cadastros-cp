import base64
import io
import json
import mimetypes
import re
import requests

from PIL import Image
import fitz

MODELO_GEMINI = "gemini-3.5-flash-lite"

PRECO_ENTRADA_USD_MILHAO = 0.30
PRECO_SAIDA_USD_MILHAO = 2.50
COTACAO_SEGURANCA_BRL_USD = 6.00

LIMITE_DOCUMENTOS_SESSAO = 60
LIMITE_ESTIMADO_BRL_SESSAO = 2.00

CAMPOS = (
    "nome",
    "cpf",
    "rg",
    "data_nascimento",
    "nome_mae",
    "endereco",
    "numero",
    "bairro",
    "cidade",
    "titulo",
    "zona",
    "secao",
    "telefone",
)

PROMPT_BASE = """
Leia visualmente este documento brasileiro de cadastro/identificação e extraia SOMENTE
os dados realmente presentes no documento.

Regras obrigatórias:
- Não invente nenhum dado.
- Se um campo não estiver visível ou não existir, devolva string vazia.
- Preserve o nome completo da pessoa e o nome completo da mãe.
- O nome do arquivo é apenas uma referência auxiliar para identificar o NOME da pessoa.
  Não use o nome do arquivo para preencher nenhum outro campo.
- Se o texto visual contradizer claramente o nome do arquivo, prefira o documento.
- CPF: somente 11 dígitos, sem pontuação.
- Título de eleitor: somente dígitos.
- Data de nascimento: DD/MM/AAAA.
- Zona e seção: somente dígitos, preservando zeros à esquerda quando visíveis.
- Telefone: somente dígitos.
- Não confunda data de emissão/validade com nascimento.
- Não confunda número de registro da CNH/RG com CPF ou título.
- Em FILIAÇÃO, identifique a mãe apenas quando houver evidência suficiente.
- Retorne exclusivamente JSON no formato solicitado.
""".strip()


def _mime_type(nome_arquivo):
    nome = str(nome_arquivo or "").lower()
    if nome.endswith(".pdf"):
        return "application/pdf"
    if nome.endswith(".png"):
        return "image/png"
    if nome.endswith(".webp"):
        return "image/webp"
    if nome.endswith(".jpg") or nome.endswith(".jpeg"):
        return "image/jpeg"
    mime, _ = mimetypes.guess_type(nome_arquivo or "")
    return mime or "application/octet-stream"


def _limpar_json_texto(texto):
    texto = str(texto or "").strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*", "", texto, flags=re.I)
        texto = re.sub(r"\s*```$", "", texto)
    return texto.strip()


def _normalizar_saida(dados):
    saida = {campo: "" for campo in CAMPOS}
    if not isinstance(dados, dict):
        return saida

    for campo in CAMPOS:
        valor = dados.get(campo, "")
        if valor is None:
            valor = ""
        saida[campo] = str(valor).strip()

    saida["nome"] = saida["nome"].upper()
    saida["nome_mae"] = saida["nome_mae"].upper()

    for campo in ("cpf", "titulo", "zona", "secao", "telefone"):
        saida[campo] = re.sub(r"\D", "", saida[campo])

    data = saida["data_nascimento"]
    m = re.search(r"(\d{2})[./-](\d{2})[./-](\d{4})", data)
    saida["data_nascimento"] = (
        f"{m.group(1)}/{m.group(2)}/{m.group(3)}" if m else ""
    )
    return saida


def calcular_custo(prompt_tokens, output_tokens):
    entrada_usd = (int(prompt_tokens or 0) / 1_000_000) * PRECO_ENTRADA_USD_MILHAO
    saida_usd = (int(output_tokens or 0) / 1_000_000) * PRECO_SAIDA_USD_MILHAO
    usd = entrada_usd + saida_usd
    brl = usd * COTACAO_SEGURANCA_BRL_USD
    return usd, brl


def pode_chamar_gemini(documentos_usados, custo_brl_estimado):
    if int(documentos_usados or 0) >= LIMITE_DOCUMENTOS_SESSAO:
        return False, (
            f"Limite de segurança atingido: {LIMITE_DOCUMENTOS_SESSAO} "
            "documentos nesta sessão."
        )
    if float(custo_brl_estimado or 0) >= LIMITE_ESTIMADO_BRL_SESSAO:
        return False, (
            f"Limite de segurança atingido: R$ "
            f"{LIMITE_ESTIMADO_BRL_SESSAO:.2f} estimados nesta sessão."
        )
    return True, ""


def _post_gemini(inline_bytes, mime, prompt, schema, api_key, timeout):
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"inlineData": {
                    "mimeType": mime,
                    "data": base64.b64encode(inline_bytes).decode("ascii"),
                }},
                {"text": prompt},
            ],
        }],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODELO_GEMINI}:generateContent"
    )
    resposta = requests.post(
        url,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        json=payload,
        timeout=timeout,
    )

    if not resposta.ok:
        try:
            detalhe = resposta.json().get("error", {}).get("message", "")
        except Exception:
            detalhe = resposta.text[:500]
        raise RuntimeError(
            f"Gemini HTTP {resposta.status_code}: {detalhe or 'erro sem detalhe'}"
        )

    bruto = resposta.json()
    candidatos = bruto.get("candidates") or []
    if not candidatos:
        motivo = bruto.get("promptFeedback", {}).get("blockReason", "")
        raise RuntimeError(
            "Gemini não retornou resposta" + (f" ({motivo})" if motivo else ".")
        )

    partes = candidatos[0].get("content", {}).get("parts", [])
    texto_resposta = "".join(
        str(parte.get("text", "") or "")
        for parte in partes if isinstance(parte, dict)
    ).strip()

    if not texto_resposta:
        raise RuntimeError("Gemini retornou resposta vazia.")

    try:
        dados = json.loads(_limpar_json_texto(texto_resposta))
    except Exception as exc:
        raise RuntimeError(
            f"Gemini retornou JSON inválido: {texto_resposta[:300]}"
        ) from exc

    usage = bruto.get("usageMetadata", {}) or {}
    prompt_tokens = int(usage.get("promptTokenCount", 0) or 0)
    output_tokens = int(
        usage.get("candidatesTokenCount", usage.get("responseTokenCount", 0)) or 0
    )
    total_tokens = int(
        usage.get("totalTokenCount", prompt_tokens + output_tokens) or 0
    )
    custo_usd, custo_brl = calcular_custo(prompt_tokens, output_tokens)

    return dados, {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "custo_usd_estimado": custo_usd,
        "custo_brl_estimado": custo_brl,
    }


def ler_documento_gemini(arquivo_bytes, nome_arquivo, api_key, timeout=25, campos_alvo=None):
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não configurada nos Secrets do Streamlit.")

    mime = _mime_type(nome_arquivo)
    campos_alvo = [
        str(c).strip() for c in (campos_alvo or CAMPOS) if str(c).strip()
    ]
    prompt = (
        PROMPT_BASE
        + "\n\nNome do arquivo para conferência auxiliar do NOME: "
        + str(nome_arquivo or "")
        + "\n\nCAMPOS PRIORITÁRIOS NESTA CONFERÊNCIA: "
        + ", ".join(campos_alvo)
        + "\nProcure com atenção especial esses campos em TODAS as páginas. "
          "Os demais podem ficar vazios; não invente dados."
    )

    schema = {
        "type": "OBJECT",
        "properties": {campo: {"type": "STRING"} for campo in CAMPOS},
        "required": list(CAMPOS),
    }

    dados, uso = _post_gemini(
        arquivo_bytes, mime, prompt, schema, api_key, timeout
    )
    return {
        "dados": _normalizar_saida(dados),
        "uso": uso,
        "modelo": MODELO_GEMINI,
    }


def _recortar_faixa_nome_ficha(arquivo_bytes, nome_arquivo):
    """
    Cria SOMENTE para a ficha cadastral um recorte da região superior onde
    fica a linha NOME. Não é usada por RG, CNH, título, PDF comum etc.
    """
    nome = str(nome_arquivo or "").lower()

    if nome.endswith(".pdf"):
        doc = fitz.open(stream=arquivo_bytes, filetype="pdf")
        if not doc.page_count:
            raise RuntimeError("PDF sem páginas.")
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        doc.close()
    else:
        img = Image.open(io.BytesIO(arquivo_bytes)).convert("RGB")

    w, h = img.size

    # A ficha separada pode trazer um pequeno pedaço do bloco anterior.
    # Esta faixa cobre SUPERVISOR/NOME e exclui a região de NOME DA MÃE.
    y1 = int(h * 0.10)
    y2 = int(h * 0.48)
    recorte = img.crop((0, y1, w, y2))

    # Amplia para favorecer a leitura da escrita manual.
    if recorte.width < 1800:
        fator = 1800 / recorte.width
        recorte = recorte.resize(
            (int(recorte.width * fator), int(recorte.height * fator)),
            Image.Resampling.LANCZOS
        )

    saida = io.BytesIO()
    recorte.save(saida, format="PNG", optimize=True)
    return saida.getvalue()


def ler_nome_ficha_gemini(arquivo_bytes, nome_arquivo, api_key, timeout=12):
    """
    Leitura ESPECIALIZADA, acionada somente quando a tela já confirmou
    semanticamente que o documento é a ficha cadastral.
    """
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não configurada nos Secrets do Streamlit.")

    recorte = _recortar_faixa_nome_ficha(arquivo_bytes, nome_arquivo)

    prompt = """
Esta imagem é um RECORTE de uma ficha cadastral manuscrita.

Sua única tarefa é transcrever o nome da pessoa escrito na linha cujo rótulo
impresso é "NOME:".

REGRAS:
- Leia SOMENTE o texto manuscrito da linha NOME.
- NÃO use ENDEREÇO.
- NÃO use CIDADE.
- NÃO use COMUNIDADE.
- NÃO use NOME DA MÃE.
- NÃO use SUPERVISOR ou SUBSUPERVISOR.
- Não complete por adivinhação.
- Preserve todas as palavras do nome que estiverem legíveis.
- Se a linha NOME não estiver visível ou não puder ser lida com segurança,
  devolva nome vazio.
- Retorne exclusivamente JSON: {"nome": "..."}.
""".strip()

    schema = {
        "type": "OBJECT",
        "properties": {"nome": {"type": "STRING"}},
        "required": ["nome"],
    }

    dados, uso = _post_gemini(
        recorte, "image/png", prompt, schema, api_key, timeout
    )

    nome = str(dados.get("nome", "") or "").strip().upper()
    return {
        "dados": {"nome": nome},
        "uso": uso,
        "modelo": MODELO_GEMINI,
    }
