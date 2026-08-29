import base64
import json
import mimetypes
import re
import requests

MODELO_GEMINI = "gemini-3.5-flash-lite"

# Preço do Gemini 2.5 Flash-Lite por 1 milhão de tokens.
# Mantido aqui, em um único lugar, para ser fácil atualizar se o Google mudar o preço.
PRECO_ENTRADA_USD_MILHAO = 0.30
PRECO_SAIDA_USD_MILHAO = 2.50

# Cotação propositalmente conservadora apenas para o painel de estimativa.
COTACAO_SEGURANCA_BRL_USD = 6.00

# Travas do PRIMEIRO TESTE.
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


def ler_documento_gemini(arquivo_bytes, nome_arquivo, api_key, timeout=25, campos_alvo=None):
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY não configurada nos Secrets do Streamlit."
        )

    mime = _mime_type(nome_arquivo)

    campos_alvo = [str(c).strip() for c in (campos_alvo or CAMPOS) if str(c).strip()]
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
        "properties": {
            "nome": {"type": "STRING"},
            "cpf": {"type": "STRING"},
            "rg": {"type": "STRING"},
            "data_nascimento": {"type": "STRING"},
            "nome_mae": {"type": "STRING"},
            "endereco": {"type": "STRING"},
            "numero": {"type": "STRING"},
            "bairro": {"type": "STRING"},
            "cidade": {"type": "STRING"},
            "titulo": {"type": "STRING"},
            "zona": {"type": "STRING"},
            "secao": {"type": "STRING"},
            "telefone": {"type": "STRING"},
        },
        "required": list(CAMPOS),
    }

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": mime,
                            "data": base64.b64encode(arquivo_bytes).decode("ascii"),
                        }
                    },
                    {"text": prompt},
                ],
            }
        ],
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
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
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
            "Gemini não retornou resposta"
            + (f" ({motivo})" if motivo else ".")
        )

    partes = candidatos[0].get("content", {}).get("parts", [])
    texto_resposta = "".join(
        str(parte.get("text", "") or "")
        for parte in partes
        if isinstance(parte, dict)
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

    return {
        "dados": _normalizar_saida(dados),
        "uso": {
            "prompt_tokens": prompt_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "custo_usd_estimado": custo_usd,
            "custo_brl_estimado": custo_brl,
        },
        "modelo": MODELO_GEMINI,
    }
