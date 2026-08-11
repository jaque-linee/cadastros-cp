import streamlit as st
import requests
import re
import io
import gc
import unicodedata
import numpy as np
import pandas as pd
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import pytesseract
import fitz
import sheets

# ============================================================
# 1. CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Sistema de Cadastro CP",
    layout="wide",
    page_icon="📋"
)


# ============================================================
# 2. CSS
# ============================================================

st.markdown(
    """
    <style>
    .stApp {
        background-color: #eef2f5 !important;
    }

    div.stButton > button {
        background-color: #0056b3 !important;
        color: white !important;
        border-radius: 12px !important;
        border: 2px solid #0056b3 !important;
        font-weight: bold !important;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    /* Inputs de texto: telefone visível e editável */
    div[data-baseweb="input"] {
        background-color: #ffffff !important;
        border: 1px solid #b8c2cc !important;
        border-radius: 8px !important;
    }

    div[data-baseweb="input"] input {
        background-color: #ffffff !important;
        color: #111827 !important;
        caret-color: #111827 !important;
        -webkit-text-fill-color: #111827 !important;
    }

    div[data-baseweb="input"]:focus-within {
        border: 2px solid #0056b3 !important;
    }

    div[data-baseweb="input"] input::placeholder {
        color: #7b8794 !important;
        opacity: 1 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# 3. WEBHOOK
# ============================================================

try:
    WEBHOOK_URL = st.secrets["WEBHOOK_URL"]

except Exception:
    st.error(
        "Erro nas chaves de segurança (Secrets) do Streamlit."
    )
    st.stop()


# ============================================================
# 4. FUNÇÕES BÁSICAS
# ============================================================

def somente_numeros(valor):
    return re.sub(
        r"\D",
        "",
        str(valor or "")
    )


def normalizar_texto(valor):
    return str(
        valor or ""
    ).strip().upper()


def remover_acentos(valor):
    valor = str(
        valor or ""
    )

    return "".join(
        caractere
        for caractere in unicodedata.normalize(
            "NFD",
            valor
        )
        if unicodedata.category(
            caractere
        ) != "Mn"
    )


def normalizar_rotulo(valor):
    valor = remover_acentos(
        valor
    ).upper()

    return re.sub(
        r"[^A-Z0-9]",
        "",
        valor
    )


def formatar_cpf(cpf):
    cpf = somente_numeros(
        cpf
    )

    if len(cpf) != 11:
        return cpf

    return (
        f"{cpf[0:3]}."
        f"{cpf[3:6]}."
        f"{cpf[6:9]}-"
        f"{cpf[9:11]}"
    )


def cpf_valido(cpf):
    """Valida CPF pelos dígitos verificadores. Não infere nem corrige números."""
    cpf = somente_numeros(cpf)

    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    for tamanho in (9, 10):
        soma = sum(
            int(cpf[i]) * (tamanho + 1 - i)
            for i in range(tamanho)
        )
        digito = (soma * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(cpf[tamanho]):
            return False

    return True


def data_valida(valor):
    """Valida uma data real no formato DD/MM/AAAA, DD-MM-AAAA ou DD.MM.AAAA."""
    from datetime import datetime

    valor = str(valor or "").strip()
    match = re.fullmatch(r"(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})", valor)

    if not match:
        return False

    try:
        datetime.strptime(
            f"{match.group(1)}/{match.group(2)}/{match.group(3)}",
            "%d/%m/%Y"
        )
        return 1900 <= int(match.group(3)) <= datetime.now().year
    except ValueError:
        return False


# ============================================================
# 4A. TELEFONE
# ============================================================

def normalizar_telefone(valor):
    numero = somente_numeros(valor)

    if len(numero) == 13 and numero.startswith("55"):
        numero = numero[2:]

    if len(numero) in (10, 11):
        return numero

    return ""


def encontrar_telefone_em_texto(texto):
    texto = str(texto or "")

    padroes = [
        r"(?<!\d)(?:\+?55[\s.\-]?)?\(?\d{2}\)?[\s.\-]?\d{4,5}[\s.\-]?\d{4}(?!\d)",
        r"(?<!\d)\d{10,11}(?!\d)"
    ]

    candidatos = []

    for padrao in padroes:
        for match in re.finditer(padrao, texto):
            telefone = normalizar_telefone(match.group(0))

            if not telefone:
                continue

            # Evita classificar CPF válido como telefone.
            if len(telefone) == 11 and cpf_valido(telefone):
                continue

            if telefone not in candidatos:
                candidatos.append(telefone)

    # Se houver mais de um número plausível, não adivinha.
    if len(candidatos) == 1:
        return candidatos[0]

    return ""


def encontrar_telefone_documento(texto, itens):
    telefone = encontrar_telefone_em_texto(texto)

    if telefone:
        return telefone

    candidatos = []

    for item in itens or []:
        telefone = encontrar_telefone_em_texto(
            item.get("texto", "")
        )

        if telefone and telefone not in candidatos:
            candidatos.append(telefone)

    if len(candidatos) == 1:
        return candidatos[0]

    return ""


def encontrar_telefone_nome_arquivo(nome_arquivo):
    nome = str(nome_arquivo or "")

    if "." in nome:
        nome = nome.rsplit(".", 1)[0]

    return encontrar_telefone_em_texto(nome)


# ============================================================
# 5. OCR
# SÓ CARREGA SE REALMENTE PRECISAR
# ============================================================

@st.cache_resource(show_spinner=False)
def carregar_ocr():
    import easyocr

    return easyocr.Reader(
        ["pt", "en"],
        gpu=False,
        verbose=False
    )


# ============================================================
# 6. PREPARAÇÃO DA IMAGEM
# ============================================================

def preparar_imagem(imagem):
    imagem = ImageOps.exif_transpose(
        imagem
    )

    imagem = imagem.convert(
        "RGB"
    )

    largura, altura = imagem.size

    if largura < 1200:
        proporcao = (
            1200 / largura
        )

        imagem = imagem.resize(
            (
                1200,
                int(
                    altura * proporcao
                )
            ),
            Image.Resampling.LANCZOS
        )

    if imagem.width > 2000:
        proporcao = (
            2000 / imagem.width
        )

        imagem = imagem.resize(
            (
                2000,
                int(
                    imagem.height
                    * proporcao
                )
            ),
            Image.Resampling.LANCZOS
        )

    return imagem


# ============================================================
# 7. OCR DE IMAGEM
# ============================================================

def executar_ocr_imagem(imagem):
    leitor = carregar_ocr()

    imagem = preparar_imagem(
        imagem
    )

    imagem_np = np.array(
        imagem
    )

    resultado = leitor.readtext(
        imagem_np,
        detail=1,
        paragraph=False,
        decoder="greedy"
    )

    itens = []

    for item in resultado:
        try:
            caixa = item[0]

            texto = str(
                item[1]
            ).strip()

            confianca = float(
                item[2]
            )

            if not texto:
                continue

            xs = [
                ponto[0]
                for ponto in caixa
            ]

            ys = [
                ponto[1]
                for ponto in caixa
            ]

            itens.append(
                {
                    "texto": texto,
                    "confianca": confianca,
                    "x": sum(xs) / len(xs),
                    "y": sum(ys) / len(ys)
                }
            )

        except Exception:
            continue

    itens.sort(
        key=lambda item: (
            round(
                item["y"] / 20
            ),
            item["x"]
        )
    )

    texto = "\n".join(
        item["texto"]
        for item in itens
    )

    del imagem_np

    gc.collect()

    return texto, itens



# ============================================================
# 7A. OCR TESSERACT - FALLBACK
# ============================================================

def executar_tesseract_imagem(imagem):
    imagem = ImageOps.exif_transpose(imagem).convert("RGB")
    largura, altura = imagem.size

    if largura < 1800:
        escala = 1800 / largura
        imagem = imagem.resize(
            (1800, int(altura * escala)),
            Image.Resampling.LANCZOS
        )

    imagem = ImageOps.grayscale(imagem)
    imagem = ImageOps.autocontrast(imagem)
    imagem = ImageEnhance.Contrast(imagem).enhance(1.35)
    imagem = imagem.filter(ImageFilter.SHARPEN)

    try:
        return pytesseract.image_to_string(
            imagem,
            lang="por+eng",
            config="--oem 3 --psm 6"
        ).strip()
    finally:
        del imagem
        gc.collect()


def extrair_dados_tesseract(texto, imagem_original=None):
    linhas = linhas_texto(texto)

    dados = {
        "nome": "",
        "cpf": "",
        "titulo": "",
        "data_nascimento": "",
        "nome_mae": "",
        "zona": "",
        "secao": "",
        "telefone": "",
        "_candidatos_mae": []
    }

    texto_norm = remover_acentos(texto).upper()

    # CPF
    for match in re.finditer(
        r"(?<!\d)(\d{3})[.\s-]?(\d{3})[.\s-]?(\d{3})[-.\s]?(\d{2})(?!\d)",
        texto
    ):
        numero = "".join(match.groups())
        if cpf_valido(numero):
            dados["cpf"] = formatar_cpf(numero)
            break

    # Nascimento
    padrao_data = r"(?<!\d)(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})(?!\d)"

    for i, linha in enumerate(linhas):
        rotulo = normalizar_rotulo(linha)
        if (
            "NASCIMENTO" in rotulo
            or "DATEOFBIRTH" in rotulo
            or rotulo == "BIRTH"
        ):
            candidatos = [linha]
            for deslocamento in (1, 2, -1):
                pos = i + deslocamento
                if 0 <= pos < len(linhas):
                    candidatos.append(linhas[pos])

            for candidato in candidatos:
                match = re.search(padrao_data, candidato)
                if match:
                    valor = (
                        f"{match.group(1)}/"
                        f"{match.group(2)}/"
                        f"{match.group(3)}"
                    )
                    if data_valida(valor):
                        dados["data_nascimento"] = valor
                        break
            if dados["data_nascimento"]:
                break

    if not dados["data_nascimento"]:
        datas = []
        for match in re.finditer(padrao_data, texto):
            valor = (
                f"{match.group(1)}/"
                f"{match.group(2)}/"
                f"{match.group(3)}"
            )
            if data_valida(valor) and valor not in datas:
                datas.append(valor)

        # Em identidade podem existir emissão e validade.
        # Só usa fallback global quando houver uma única data.
        if len(datas) == 1:
            dados["data_nascimento"] = datas[0]

    # Mãe com rótulo explícito no texto linear
    for i, linha in enumerate(linhas):
        rotulo = normalizar_rotulo(linha)
        if (
            rotulo in ("MAE", "NOMEDAMAE", "NOMEMAE")
            or "NOMEDAMAE" in rotulo
        ):
            for deslocamento in (1, 2, 3):
                pos = i + deslocamento
                if pos < len(linhas) and parece_nome(linhas[pos]):
                    dados["nome_mae"] = linhas[pos].strip().upper()
                    break
            if dados["nome_mae"]:
                break

    # Se FILIAÇÃO foi reconhecida no texto linear, usa os nomes próximos,
    # mas não assume automaticamente que o primeiro é a mãe.
    # A identificação segura é feita abaixo pelo OCR posicional.
    #
    # Para CIN/RG, usa pytesseract.image_to_data para recuperar caixas e linhas.
    # Isso evita depender da ordem embaralhada do texto corrido.
    if (
        not dados["nome_mae"]
        and imagem_original is not None
    ):
        try:
            imagem_pos = ImageOps.exif_transpose(
                imagem_original
            ).convert("RGB")

            largura, altura = imagem_pos.size

            if largura < 1800:
                escala = 1800 / largura
                imagem_pos = imagem_pos.resize(
                    (
                        1800,
                        int(altura * escala)
                    ),
                    Image.Resampling.LANCZOS
                )

            dados_pos = pytesseract.image_to_data(
                imagem_pos,
                lang="por+eng",
                config="--oem 3 --psm 11",
                output_type=pytesseract.Output.DICT
            )

            palavras = []

            for idx, palavra in enumerate(dados_pos.get("text", [])):
                palavra = str(palavra or "").strip()

                if not palavra:
                    continue

                try:
                    conf = float(dados_pos["conf"][idx])
                except Exception:
                    conf = -1

                if conf < 15:
                    continue

                palavras.append({
                    "texto": palavra,
                    "left": int(dados_pos["left"][idx]),
                    "top": int(dados_pos["top"][idx]),
                    "width": int(dados_pos["width"][idx]),
                    "height": int(dados_pos["height"][idx]),
                    "block": int(dados_pos["block_num"][idx]),
                    "par": int(dados_pos["par_num"][idx]),
                    "line": int(dados_pos["line_num"][idx])
                })

            # Reconstrói linhas físicas do documento.
            grupos = {}

            for p in palavras:
                chave = (
                    p["block"],
                    p["par"],
                    p["line"]
                )
                grupos.setdefault(chave, []).append(p)

            linhas_pos = []

            for grupo in grupos.values():
                grupo = sorted(
                    grupo,
                    key=lambda x: x["left"]
                )

                texto_linha = " ".join(
                    p["texto"]
                    for p in grupo
                ).strip()

                if not texto_linha:
                    continue

                linhas_pos.append({
                    "texto": texto_linha,
                    "norm": remover_acentos(
                        texto_linha
                    ).upper(),
                    "top": min(
                        p["top"]
                        for p in grupo
                    ),
                    "bottom": max(
                        p["top"] + p["height"]
                        for p in grupo
                    ),
                    "left": min(
                        p["left"]
                        for p in grupo
                    )
                })

            linhas_pos.sort(
                key=lambda x: (
                    x["top"],
                    x["left"]
                )
            )

            # Primeiro tenta localizar FILIAÇÃO/FILIATION fisicamente.
            indice_filiacao = None

            for idx, linha_pos in enumerate(linhas_pos):
                norm = normalizar_rotulo(
                    linha_pos["texto"]
                )

                if (
                    "FILIACAO" in norm
                    or "FILIATION" in norm
                ):
                    indice_filiacao = idx
                    break

            candidatos_filiacao = []

            if indice_filiacao is not None:
                topo_rotulo = linhas_pos[
                    indice_filiacao
                ]["top"]

                # Examina somente uma faixa abaixo do rótulo.
                limite = topo_rotulo + int(
                    imagem_pos.size[1] * 0.20
                )

                for linha_pos in linhas_pos[
                    indice_filiacao + 1:
                ]:
                    if linha_pos["top"] > limite:
                        break

                    candidato = linha_pos[
                        "texto"
                    ].strip()

                    if parece_nome(candidato):
                        candidatos_filiacao.append(
                            candidato.upper()
                        )

            # Caso o rótulo FILIAÇÃO não tenha sido reconhecido,
            # usa a geometria do CIN: nomes da filiação aparecem
            # acima da linha do titular e antes dos campos de emissão.
            if not candidatos_filiacao:
                nomes_pos = []

                termos_excluir = (
                    "REPUBLICA", "FEDERATIVA",
                    "BRASIL", "GOVERNO",
                    "FEDERAL", "ESTADO",
                    "SECRETARIA", "SEGURANCA",
                    "PUBLICA", "INSTITUTO",
                    "IDENTIFICACAO", "DELEGADO",
                    "REGISTRO", "GERAL",
                    "PERSONAL", "NUMBER",
                    "NOME SOCIAL", "SOCIAL NAME",
                    "CARD ISSUER", "LOCAL",
                    "PLACE", "ISSUE", "EMISSAO",
                    "NASCIMENTO", "BIRTH",
                    "NACIONALIDADE", "NATIONALITY",
                    "NATURALIDADE", "VALIDADE",
                    "EXPIRY", "ASSINATURA",
                    "SIGNATURE", "SUPERINTENDENTE"
                )

                for linha_pos in linhas_pos:
                    candidato = linha_pos[
                        "texto"
                    ].strip()

                    norm = remover_acentos(
                        candidato
                    ).upper()

                    if not parece_nome(candidato):
                        continue

                    if any(
                        termo in norm
                        for termo in termos_excluir
                    ):
                        continue

                    quantidade = len(
                        candidato.split()
                    )

                    if 3 <= quantidade <= 7:
                        nomes_pos.append(
                            linha_pos
                        )

                # Guarda nomes reconhecidos fisicamente como possíveis
                # candidatos de filiação. Isso será usado apenas para
                # conferência manual quando o OCR não conseguir distinguir
                # automaticamente qual deles é a mãe.
                candidatos_manuais = []

                for linha_nome in nomes_pos:
                    nome_candidato = (
                        str(linha_nome.get("texto", ""))
                        .strip()
                        .upper()
                    )

                    if (
                        nome_candidato
                        and nome_candidato not in candidatos_manuais
                    ):
                        candidatos_manuais.append(
                            nome_candidato
                        )

                dados["_candidatos_mae"] = candidatos_manuais

                # Procura o titular conhecido pelo OCR principal/texto.
                # Em CIN, os dois nomes imediatamente acima dele formam
                # o bloco de filiação. A linha mais próxima do titular
                # costuma ser a mãe no layout vertical; se a geometria
                # não for clara, não preenche.
                titular_idx = None

                for idx, linha_pos in enumerate(
                    nomes_pos
                ):
                    norm_nome = remover_acentos(
                        linha_pos["texto"]
                    ).upper()

                    # Nome do titular tende a aparecer depois dos dois pais
                    # e próximo dos rótulos Nome/Nome Social.
                    proximos = [
                        l["norm"]
                        for l in linhas_pos
                        if (
                            l["top"]
                            <= linha_pos["top"]
                            <= l["bottom"] + 10
                        )
                    ]

                    if any(
                        "NOME" in p
                        for p in proximos
                    ):
                        titular_idx = idx
                        break

                # Se a linha do titular não foi localizada pelo rótulo,
                # usa três nomes completos consecutivos no topo da área
                # de dados, mas só quando a separação vertical confirma
                # que os dois primeiros pertencem ao mesmo bloco.
                if (
                    titular_idx is not None
                    and titular_idx >= 2
                ):
                    pais = nomes_pos[
                        titular_idx - 2:
                        titular_idx
                    ]

                    if len(pais) == 2:
                        # No CIN brasileiro o campo Filiação não identifica
                        # sexo do genitor no texto OCR. Sem o rótulo individual,
                        # não é seguro decidir qual dos dois é a mãe.
                        # Portanto não inventa.
                        candidatos_filiacao = []

            # Só preenche automaticamente quando há um único candidato
            # inequivocamente associado ao campo Mãe.
            if len(candidatos_filiacao) == 1:
                dados["nome_mae"] = (
                    candidatos_filiacao[0]
                )

            del imagem_pos
            gc.collect()

        except Exception:
            pass

    if not dados["telefone"]:
        dados["telefone"] = encontrar_telefone_em_texto(
            texto
        )

    return dados


def combinar_dados_ocr(principal, fallback):
    resultado = dict(principal)

    for campo in (
        "nome", "cpf", "titulo", "data_nascimento",
        "nome_mae", "zona", "secao", "telefone"
    ):
        if not resultado.get(campo) and fallback.get(campo):
            resultado[campo] = fallback[campo]

    return resultado


# ============================================================
# 8. EXTRAIR TEXTO NATIVO DO PDF
# ============================================================

def extrair_texto_pdf(arquivo):
    arquivo.seek(0)

    bytes_pdf = arquivo.getvalue()

    documento = fitz.open(
        stream=bytes_pdf,
        filetype="pdf"
    )

    textos = []

    for pagina in documento:
        texto = pagina.get_text(
            "text"
        )

        if texto:
            textos.append(
                texto.strip()
            )

    documento.close()

    return "\n".join(
        textos
    ).strip()


# ============================================================
# 9. VERIFICAR SE O TEXTO NATIVO É REALMENTE ÚTIL
# ============================================================

def pdf_tem_texto_util(texto):
    if not texto:
        return False

    texto_normalizado = remover_acentos(
        texto
    ).upper()

    texto_sem_espacos = re.sub(
        r"\s",
        "",
        texto_normalizado
    )

    if len(
        texto_sem_espacos
    ) < 30:
        return False

    pontos = 0

    if re.search(
        r"\b\d{2}[\/.\-]\d{2}[\/.\-]\d{4}\b",
        texto
    ):
        pontos += 1

    if "CPF" in texto_normalizado:
        pontos += 1

    if (
        "INSCRICAO" in texto_normalizado
        or "TITULO" in texto_normalizado
    ):
        pontos += 1

    if "NOME" in texto_normalizado:
        pontos += 1

    if (
        "FILIACAO" in texto_normalizado
        or "MAE" in texto_normalizado
        or "NOME DA MAE" in texto_normalizado
    ):
        pontos += 1

    if (
        "CARTEIRA NACIONAL" in texto_normalizado
        or "HABILITACAO" in texto_normalizado
        or "REGISTRO" in texto_normalizado
    ):
        pontos += 1

    if (
        "IDENTIDADE" in texto_normalizado
        or "REGISTRO GERAL" in texto_normalizado
    ):
        pontos += 1

    return pontos >= 2


# ============================================================
# 10. OCR DE PDF ESCANEADO
# ============================================================

def executar_ocr_pdf(arquivo):
    arquivo.seek(0)

    bytes_pdf = arquivo.getvalue()

    documento = fitz.open(
        stream=bytes_pdf,
        filetype="pdf"
    )

    textos = []
    todos_itens = []

    for numero_pagina in range(
        len(documento)
    ):
        pagina = documento[
            numero_pagina
        ]

        pix = pagina.get_pixmap(
            matrix=fitz.Matrix(
                1.25,
                1.25
            ),
            alpha=False
        )

        bytes_imagem = pix.tobytes(
            "jpeg"
        )

        imagem = Image.open(
            io.BytesIO(
                bytes_imagem
            )
        ).convert(
            "RGB"
        )

        texto, itens = executar_ocr_imagem(
            imagem
        )

        if texto:
            textos.append(
                texto
            )

        todos_itens.extend(
            itens
        )

        del imagem
        del pix
        del bytes_imagem

        gc.collect()

    documento.close()

    return (
        "\n".join(
            textos
        ),
        todos_itens
    )


# ============================================================
# 11. LER DOCUMENTO
# ============================================================

def ler_documento(arquivo):
    nome = arquivo.name.lower()

    if nome.endswith(
        ".pdf"
    ):
        texto_nativo = extrair_texto_pdf(
            arquivo
        )

        if pdf_tem_texto_util(
            texto_nativo
        ):
            return (
                texto_nativo,
                [],
                "PDF — texto digital"
            )

        texto, itens = executar_ocr_pdf(
            arquivo
        )

        return (
            texto,
            itens,
            "PDF — OCR"
        )

    arquivo.seek(0)

    imagem = Image.open(
        arquivo
    )

    texto, itens = executar_ocr_imagem(
        imagem
    )

    del imagem

    gc.collect()

    return (
        texto,
        itens,
        "Imagem — OCR"
    )


# ============================================================
# 12. LINHAS DO TEXTO
# ============================================================

def linhas_texto(texto):
    return [
        linha.strip()
        for linha in str(
            texto or ""
        ).splitlines()
        if linha.strip()
    ]


# ============================================================
# 13. IDENTIFICAR RÓTULOS
# ============================================================

def eh_rotulo_documento(texto):
    valor = normalizar_rotulo(
        texto
    )

    rotulos = [
        "NOMEDOELEITOR",
        "NOME",
        "NOMECOMPLETO",
        "DATADENASCIMENTO",
        "NASCIMENTO",
        "INSCRICAO",
        "TITULO",
        "ZONA",
        "SECAO",
        "FILIACAO",
        "PAI",
        "MAE",
        "NOMEDAMAE",
        "NOMEDOPAI",
        "MUNICIPIOUF",
        "DATADEEMISSAO",
        "CPF",
        "RG",
        "IDENTIDADE",
        "REGISTRO",
        "VALIDADE",
        "HABILITACAO",
        "CARTEIRANACIONALDEHABILITACAO"
    ]

    return valor in rotulos


# ============================================================
# 14. VERIFICAR SE PARECE NOME
# ============================================================

def parece_nome(texto):
    texto = str(
        texto or ""
    ).strip()

    if not texto:
        return False

    if re.search(
        r"\d",
        texto
    ):
        return False

    normalizado = normalizar_rotulo(
        texto
    )

    ignorar = [
        "REPUBLICA",
        "FEDERATIVA",
        "BRASIL",
        "JUSTICA",
        "ELEITORAL",
        "TITULO",
        "IDENTIFICACAO",
        "BIOMETRICA",
        "NOME",
        "NOMEDOELEITOR",
        "NOMECOMPLETO",
        "DATADENASCIMENTO",
        "NASCIMENTO",
        "INSCRICAO",
        "CPF",
        "RG",
        "ZONA",
        "SECAO",
        "MUNICIPIO",
        "EMISSAO",
        "VALIDADE",
        "VALIDOSOMENTE",
        "MARCADAGUA",
        "AUTENTICIDADE",
        "DOCUMENTO",
        "PODERA",
        "CONFERIDA",
        "ORIENTACOES",
        "CARTEIRA",
        "NACIONAL",
        "HABILITACAO",
        "REGISTRO",
        "FILIACAO",
        "ASSINATURA",
        "PERMISSAO",
        "CATEGORIA"
    ]

    for termo in ignorar:
        if termo in normalizado:
            return False

    palavras = texto.split()

    if not (
        2 <= len(palavras) <= 8
    ):
        return False

    letras = re.sub(
        r"[^A-Za-zÀ-ÿ]",
        "",
        texto
    )

    if len(letras) < 7:
        return False

    return True


# ============================================================
# 15. EXTRAIR NOME DA MÃE DE TEXTO DIGITAL
# ============================================================

def encontrar_mae_texto_digital(linhas):
    for i, linha in enumerate(linhas):
        rotulo = normalizar_rotulo(linha)

        if rotulo in ("MAE", "NOMEDAMAE", "NOMEMAE"):
            for deslocamento in (1, 2):
                pos = i + deslocamento
                if pos < len(linhas) and parece_nome(linhas[pos]):
                    return linhas[pos].upper()

            if i > 0 and parece_nome(linhas[i - 1]):
                return linhas[i - 1].upper()

    return ""


# ============================================================
# 16. EXTRAIR DADOS DO PDF DIGITAL
# ============================================================

def extrair_dados_pdf_digital(texto):
    linhas = linhas_texto(texto)

    dados = {
        "nome": "",
        "cpf": "",
        "titulo": "",
        "data_nascimento": "",
        "nome_mae": "",
        "zona": "",
        "secao": "",
        "telefone": ""
    }

    texto_norm = remover_acentos(texto).upper()

    eh_titulo = (
        "JUSTICA ELEITORAL" in texto_norm
        or "TITULO ELEITORAL" in texto_norm
    )

    eh_cnh = (
        "CARTEIRA NACIONAL" in texto_norm
        or "HABILITACAO" in texto_norm
        or "DENATRAN" in texto_norm
    )

    # 1. NOME
    for i, linha in enumerate(linhas):
        rotulo = normalizar_rotulo(linha)

        if rotulo in (
            "NOMEDOELEITOR",
            "NOME",
            "NOMECOMPLETO"
        ):
            if i + 1 < len(linhas):
                candidato = linhas[i + 1].strip()

                if parece_nome(candidato):
                    dados["nome"] = candidato.upper()
                    break

            if i > 0:
                candidato = linhas[i - 1].strip()

                if parece_nome(candidato):
                    dados["nome"] = candidato.upper()
                    break

    if not dados["nome"]:
        for linha in linhas:
            if parece_nome(linha):
                rotulo = normalizar_rotulo(linha)

                if not any(
                    termo in rotulo
                    for termo in (
                        "REPUBLICA",
                        "FEDERATIVA",
                        "JUSTICA",
                        "ELEITORAL",
                        "CARTEIRA",
                        "NACIONAL",
                        "HABILITACAO"
                    )
                ):
                    dados["nome"] = linha.upper()
                    break

    # 2. DATA DE NASCIMENTO
    for i, linha in enumerate(linhas):
        rotulo = normalizar_rotulo(linha)

        if (
            "DATADENASCIMENTO" in rotulo
            or rotulo == "NASCIMENTO"
            or rotulo == "DATANASCIMENTO"
        ):
            candidatos = []

            for deslocamento in (1, 2):
                pos = i + deslocamento

                if pos < len(linhas):
                    match = re.search(
                        r"\b(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})\b",
                        linhas[pos]
                    )

                    if match:
                        valor = (
                            f"{match.group(1)}/"
                            f"{match.group(2)}/"
                            f"{match.group(3)}"
                        )

                        if data_valida(valor):
                            candidatos.append(valor)

            if i > 0:
                match = re.search(
                    r"\b(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})\b",
                    linhas[i - 1]
                )

                if match:
                    valor = (
                        f"{match.group(1)}/"
                        f"{match.group(2)}/"
                        f"{match.group(3)}"
                    )

                    if data_valida(valor):
                        candidatos.append(valor)

            if candidatos:
                dados["data_nascimento"] = candidatos[0]
                break

    if not dados["data_nascimento"]:
        for linha in linhas:
            match = re.search(
                r"\b(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})\b",
                linha
            )

            if match:
                valor = (
                    f"{match.group(1)}/"
                    f"{match.group(2)}/"
                    f"{match.group(3)}"
                )

                if data_valida(valor):
                    dados["data_nascimento"] = valor
                    break

    # 3. CPF
    for i, linha in enumerate(linhas):
        rotulo = normalizar_rotulo(linha)

        if "CPF" in rotulo:
            candidatos = [linha]

            if i + 1 < len(linhas):
                candidatos.append(linhas[i + 1])

            if i + 2 < len(linhas):
                candidatos.append(linhas[i + 2])

            for candidato in candidatos:
                numeros = somente_numeros(candidato)

                if len(numeros) == 11 and cpf_valido(numeros):
                    dados["cpf"] = formatar_cpf(numeros)
                    break

            if dados["cpf"]:
                break

    if not dados["cpf"]:
        for linha in linhas:
            numeros = somente_numeros(linha)

            if len(numeros) == 11 and cpf_valido(numeros):
                dados["cpf"] = formatar_cpf(numeros)
                break

    # 4. TÍTULO ELEITORAL
    if eh_titulo:
        for i, linha in enumerate(linhas):
            rotulo = normalizar_rotulo(linha)

            if (
                "INSCRICAO" in rotulo
                or rotulo == "TITULO"
                or rotulo == "TITULODEELEITOR"
            ):
                candidatos = [linha]

                for deslocamento in (1, 2, -1):
                    pos = i + deslocamento

                    if 0 <= pos < len(linhas):
                        candidatos.append(linhas[pos])

                for candidato in candidatos:
                    numero = somente_numeros(candidato)

                    if len(numero) == 12:
                        dados["titulo"] = numero
                        break

                if dados["titulo"]:
                    break

    # 5. ZONA E SEÇÃO
    if eh_titulo:
        def extrair_numero_associado_ao_rotulo(
            linhas,
            nome_rotulo,
            max_digitos
        ):
            for i, linha in enumerate(linhas):
                rotulo = normalizar_rotulo(linha)

                if rotulo != nome_rotulo:
                    continue

                if i > 0:
                    candidato = linhas[i - 1].strip()

                    if re.fullmatch(
                        r"\d{1," + str(max_digitos) + r"}",
                        candidato
                    ):
                        return candidato.zfill(
                            max_digitos
                        )

                linha_sem_acento = remover_acentos(
                    linha
                ).upper()

                match = re.search(
                    r"\b"
                    + nome_rotulo
                    + r"\b\s*[:\-]?\s*(\d{1,"
                    + str(max_digitos)
                    + r"})\b",
                    linha_sem_acento
                )

                if match:
                    return match.group(1).zfill(
                        max_digitos
                    )

                if i + 1 < len(linhas):
                    candidato = linhas[i + 1].strip()

                    if re.fullmatch(
                        r"\d{1," + str(max_digitos) + r"}",
                        candidato
                    ):
                        return candidato.zfill(
                            max_digitos
                        )

            return ""

        zona_encontrada = (
            extrair_numero_associado_ao_rotulo(
                linhas,
                "ZONA",
                3
            )
        )

        secao_encontrada = (
            extrair_numero_associado_ao_rotulo(
                linhas,
                "SECAO",
                4
            )
        )

        if zona_encontrada:
            dados["zona"] = zona_encontrada

        if secao_encontrada:
            dados["secao"] = secao_encontrada

    # 6. NOME DA MÃE
    for i, linha in enumerate(linhas):
        rotulo = normalizar_rotulo(linha)

        if rotulo in (
            "MAE",
            "NOMEDAMAE",
            "NOMEMAE"
        ):
            partes = []

            for deslocamento in range(1, 5):
                pos = i + deslocamento

                if pos >= len(linhas):
                    break

                candidato = linhas[pos].strip()
                candidato_rotulo = normalizar_rotulo(candidato)

                if eh_rotulo_documento(candidato):
                    break

                if re.search(r"\d", candidato):
                    break

                if parece_nome(candidato):
                    partes.append(candidato.upper())
                elif partes:
                    break

            if partes:
                dados["nome_mae"] = " ".join(partes)
                break

    if eh_titulo and not dados["nome_mae"]:
        indice_filiacao = None

        for i, linha in enumerate(linhas):
            if normalizar_rotulo(linha) == "FILIACAO":
                indice_filiacao = i
                break

        if indice_filiacao is not None:
            candidatos = []

            inicio = max(0, indice_filiacao - 3)
            fim = min(len(linhas), indice_filiacao + 5)

            for pos in range(inicio, fim):
                if pos == indice_filiacao:
                    continue

                candidato = linhas[pos].strip()

                if candidato.upper() == dados["nome"]:
                    continue

                if eh_rotulo_documento(candidato):
                    continue

                if re.search(r"\d", candidato):
                    continue

                if parece_nome(candidato):
                    candidatos.append(
                        (
                            pos,
                            candidato.upper()
                        )
                    )

            nomes_unicos = []

            for _, candidato in candidatos:
                if candidato not in nomes_unicos:
                    nomes_unicos.append(candidato)

            if nomes_unicos:
                dados["nome_mae"] = nomes_unicos[0]

    if eh_cnh and not dados["nome_mae"]:
        indice_filiacao = None

        for i, linha in enumerate(linhas):
            if normalizar_rotulo(linha) == "FILIACAO":
                indice_filiacao = i
                break

        if indice_filiacao is not None:
            bloco_filiacao = []

            rotulos_fim = (
                "PERMISSAO",
                "ACC",
                "CATHAB",
                "CATEGORIA",
                "REGISTRO",
                "VALIDADE",
                "HABILITACAO",
                "OBSERVACOES",
                "LOCAL",
                "DATAEMISSAO",
                "ASSINATURA"
            )

            for pos in range(
                indice_filiacao + 1,
                min(len(linhas), indice_filiacao + 10)
            ):
                candidato = linhas[pos].strip()
                rotulo = normalizar_rotulo(candidato)

                if any(
                    rotulo.startswith(fim)
                    for fim in rotulos_fim
                ):
                    break

                if not candidato:
                    continue

                if re.search(r"\d", candidato):
                    continue

                if candidato.upper() == dados["nome"]:
                    continue

                if parece_nome(candidato):
                    bloco_filiacao.append(candidato.upper())
                    continue

                if re.fullmatch(
                    r"[A-Za-zÀ-ÿ\s]+",
                    candidato
                ):
                    palavras = candidato.split()

                    if palavras:
                        bloco_filiacao.append(candidato.upper())

            if len(bloco_filiacao) >= 2:
                possibilidades = []

                for corte in range(1, len(bloco_filiacao)):
                    parte_1 = " ".join(
                        bloco_filiacao[:corte]
                    ).strip()

                    parte_2 = " ".join(
                        bloco_filiacao[corte:]
                    ).strip()

                    if not parece_nome(parte_1):
                        continue

                    if not parece_nome(parte_2):
                        continue

                    palavras_1 = len(parte_1.split())
                    palavras_2 = len(parte_2.split())

                    diferenca = abs(
                        palavras_1 - palavras_2
                    )

                    possibilidades.append(
                        (
                            diferenca,
                            corte,
                            parte_2
                        )
                    )

                if possibilidades:
                    possibilidades.sort(
                        key=lambda item: (
                            item[0],
                            item[1]
                        )
                    )

                    dados["nome_mae"] = (
                        possibilidades[0][2]
                    )

    dados["telefone"] = encontrar_telefone_em_texto(
        texto
    )

    return dados


# ============================================================
# 17. EXTRAÇÃO OCR - TÍTULO
# ============================================================

def encontrar_titulo_ocr(itens):
    rotulos = []

    for item in itens:
        rotulo = normalizar_rotulo(item["texto"])
        if (
            rotulo in ("INSCRICAO", "TITULO", "TITULODEELEITOR")
            or "INSCRICAO" in rotulo
        ):
            rotulos.append(item)

    for rotulo in rotulos:
        candidatos = []

        numero_no_rotulo = somente_numeros(rotulo["texto"])
        if len(numero_no_rotulo) == 12:
            candidatos.append((0, -rotulo["confianca"], numero_no_rotulo))

        for item in itens:
            if item is rotulo:
                continue

            numero = somente_numeros(item["texto"])
            if len(numero) != 12:
                continue

            dx = abs(item["x"] - rotulo["x"])
            dy = item["y"] - rotulo["y"]

            if -50 <= dy <= 180 and dx <= 550:
                candidatos.append(
                    (abs(dy) + dx * 0.25, -item["confianca"], numero)
                )

        if candidatos:
            candidatos.sort()
            return candidatos[0][2]

    return ""


# ============================================================
# 18. EXTRAÇÃO OCR - NASCIMENTO
# ============================================================

def encontrar_nascimento_ocr(itens):
    rotulos = []

    for item in itens:
        rotulo = normalizar_rotulo(item["texto"])
        if (
            "NASCIMENTO" in rotulo
            or "DATEOFBIRTH" in rotulo
            or "BIRTH" in rotulo
        ):
            rotulos.append(item)

    padrao_data = r"(?<!\d)(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})(?!\d)"

    for rotulo in rotulos:
        candidatos = []

        # A data pode ter sido reconhecida no mesmo bloco do rótulo.
        for match in re.finditer(padrao_data, str(rotulo["texto"])):
            valor = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
            if data_valida(valor):
                candidatos.append((0, -rotulo["confianca"], valor))

        # Ou em um bloco próximo, normalmente abaixo ou ao lado do rótulo.
        for item in itens:
            texto_item = str(item["texto"])

            for match in re.finditer(padrao_data, texto_item):
                valor = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                if not data_valida(valor):
                    continue

                dx = abs(item["x"] - rotulo["x"])
                dy = item["y"] - rotulo["y"]

                if -80 <= dy <= 260 and dx <= 800:
                    candidatos.append(
                        (abs(dy) + dx * 0.15, -item["confianca"], valor)
                    )

        if candidatos:
            candidatos.sort()
            return candidatos[0][2]

    # Fallback conservador: se só houver uma data válida no documento,
    # ela pode ser usada como nascimento. Com várias datas, não adivinha.
    datas = []

    for item in itens:
        for match in re.finditer(padrao_data, str(item["texto"])):
            valor = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
            if data_valida(valor) and valor not in datas:
                datas.append(valor)

    if len(datas) == 1:
        return datas[0]

    return ""


# ============================================================
# 19. EXTRAÇÃO OCR - CPF
# ============================================================

def encontrar_cpf_ocr(itens):
    for item_rotulo in itens:
        texto_rotulo = normalizar_texto(
            item_rotulo["texto"]
        )

        if "CPF" not in texto_rotulo:
            continue

        candidatos = []

        for item in itens:
            numero = somente_numeros(
                item["texto"]
            )

            if len(numero) != 11 or not cpf_valido(numero):
                continue

            dx = abs(
                item["x"]
                - item_rotulo["x"]
            )

            dy = abs(
                item["y"]
                - item_rotulo["y"]
            )

            if (
                dx <= 500
                and dy <= 200
            ):
                candidatos.append(
                    (
                        dy + dx,
                        -item["confianca"],
                        numero
                    )
                )

        if candidatos:
            candidatos.sort()

            return formatar_cpf(
                candidatos[0][2]
            )

    for item in itens:
        numero = somente_numeros(
            item["texto"]
        )

        if len(numero) == 11 and cpf_valido(numero):
            return formatar_cpf(
                numero
            )

    return ""


# ============================================================
# 20. EXTRAÇÃO OCR - NOME
# ============================================================

def encontrar_nome_ocr(itens):
    for item_rotulo in itens:
        rotulo = normalizar_rotulo(
            item_rotulo["texto"]
        )

        if (
            "NOMEDOELEITOR" in rotulo
            or rotulo == "NOME"
            or rotulo == "NOMECOMPLETO"
        ):
            candidatos = []

            for item in itens:
                if item is item_rotulo:
                    continue

                candidato = item[
                    "texto"
                ].strip()

                if not parece_nome(
                    candidato
                ):
                    continue

                dy = (
                    item["y"]
                    - item_rotulo["y"]
                )

                dx = abs(
                    item["x"]
                    - item_rotulo["x"]
                )

                if (
                    -40 <= dy <= 220
                    and dx <= 600
                ):
                    candidatos.append(
                        (
                            abs(dy) + dx * 0.2,
                            -item["confianca"],
                            candidato
                        )
                    )

            if candidatos:
                candidatos.sort()

                return (
                    candidatos[0][2]
                    .strip()
                    .upper()
                )

    candidatos = []

    for item in itens:
        candidato = item[
            "texto"
        ].strip()

        if parece_nome(
            candidato
        ):
            palavras = len(
                candidato.split()
            )

            pontuacao = (
                palavras * 20
                + item["confianca"] * 20
            )

            candidatos.append(
                (
                    pontuacao,
                    candidato.upper()
                )
            )

    if candidatos:
        candidatos.sort(
            reverse=True
        )

        return candidatos[0][1]

    return ""


# ============================================================
# 21. EXTRAÇÃO OCR - NOME DA MÃE
# ============================================================

def encontrar_mae_ocr(itens):
    # 1. Prioridade máxima: documento que identifica explicitamente a mãe.
    rotulos_mae = []

    for item in itens:
        rotulo = normalizar_rotulo(item["texto"])
        if (
            rotulo in ("MAE", "NOMEDAMAE", "NOMEMAE")
            or "NOMEDAMAE" in rotulo
            or rotulo.startswith("MAE")
        ):
            rotulos_mae.append(item)

    for rotulo in rotulos_mae:
        candidatos = []

        for item in itens:
            if item is rotulo:
                continue

            candidato = str(item["texto"]).strip()

            if not parece_nome(candidato):
                continue

            dx = abs(item["x"] - rotulo["x"])
            dy = item["y"] - rotulo["y"]

            if -60 <= dy <= 260 and dx <= 800:
                candidatos.append(
                    (
                        abs(dy) + dx * 0.15,
                        -item["confianca"],
                        candidato.upper()
                    )
                )

        if candidatos:
            candidatos.sort()
            return candidatos[0][2]

    # 2. RG/CIN e outros documentos podem trazer apenas FILIAÇÃO/FILIATION.
    # Nesses documentos, captura o primeiro nome completo associado ao campo,
    # sem usar lista de nomes próprios nem inventar conteúdo.
    rotulos_filiacao = []

    for item in itens:
        rotulo = normalizar_rotulo(item["texto"])
        if "FILIACAO" in rotulo or "FILIATION" in rotulo:
            rotulos_filiacao.append(item)

    for rotulo in rotulos_filiacao:
        candidatos = []

        for item in itens:
            if item is rotulo:
                continue

            candidato = str(item["texto"]).strip()

            if not parece_nome(candidato):
                continue

            dx = abs(item["x"] - rotulo["x"])
            dy = item["y"] - rotulo["y"]

            # Campo de filiação costuma ficar imediatamente abaixo do rótulo.
            if -30 <= dy <= 300 and dx <= 850:
                candidatos.append(
                    (
                        max(dy, 0) * 2 + dx * 0.10,
                        item["y"],
                        item["x"],
                        -item["confianca"],
                        candidato.upper()
                    )
                )

        if candidatos:
            candidatos.sort()
            return candidatos[0][4]

    return ""


# ============================================================
# 22. ZONA E SEÇÃO OCR
# ============================================================

def encontrar_zona_secao_ocr(
    itens,
    titulo
):
    zona = ""
    secao = ""

    rotulo_zona = None
    rotulo_secao = None

    for item in itens:
        rotulo = normalizar_rotulo(
            item["texto"]
        )

        if rotulo == "ZONA":
            rotulo_zona = item

        if rotulo == "SECAO":
            rotulo_secao = item

    def procurar_valor(
        rotulo,
        max_digitos
    ):
        if rotulo is None:
            return ""

        candidatos = []

        for item in itens:
            if item is rotulo:
                continue

            texto = item[
                "texto"
            ]

            if re.search(
                r"\d{2}[\/.\-]\d{2}[\/.\-]\d{4}",
                texto
            ):
                continue

            numero = somente_numeros(
                texto
            )

            if not (
                1 <= len(numero)
                <= max_digitos
            ):
                continue

            if numero == titulo:
                continue

            dy = (
                item["y"]
                - rotulo["y"]
            )

            dx = abs(
                item["x"]
                - rotulo["x"]
            )

            if not (
                0 < dy <= 160
            ):
                continue

            if dx > 130:
                continue

            candidatos.append(
                (
                    dx * 4 + dy,
                    -item["confianca"],
                    numero
                )
            )

        if candidatos:
            candidatos.sort()

            return candidatos[
                0
            ][2]

        return ""

    zona = procurar_valor(
        rotulo_zona,
        3
    )

    secao = procurar_valor(
        rotulo_secao,
        4
    )

    if zona:
        zona = zona.zfill(
            3
        )

    if secao:
        secao = secao.zfill(
            4
        )

    return zona, secao


# ============================================================
# 23. EXTRAIR DADOS OCR
# ============================================================

def extrair_dados_ocr(
    texto,
    itens
):
    titulo = encontrar_titulo_ocr(
        itens
    )

    nome = encontrar_nome_ocr(
        itens
    )

    cpf = encontrar_cpf_ocr(
        itens
    )

    nascimento = encontrar_nascimento_ocr(
        itens
    )

    nome_mae = encontrar_mae_ocr(
        itens
    )

    zona, secao = encontrar_zona_secao_ocr(
        itens,
        titulo
    )

    return {
        "nome": nome,
        "cpf": cpf,
        "titulo": titulo,
        "data_nascimento": nascimento,
        "nome_mae": nome_mae,
        "zona": zona,
        "secao": secao,
        "telefone": encontrar_telefone_documento(
            texto,
            itens
        )
    }


# ============================================================
# 24. EXTRAÇÃO GERAL
# ============================================================

def extrair_dados(
    texto,
    itens,
    tipo_leitura
):
    if (
        tipo_leitura
        == "PDF — texto digital"
    ):
        return extrair_dados_pdf_digital(
            texto
        )

    return extrair_dados_ocr(
        texto,
        itens
    )


# ============================================================
# 25. CARREGAR BASE DO SHEETS
# ============================================================

@st.cache_data(ttl=60)
def carregar_base():
    try:
        resposta = requests.get(
            WEBHOOK_URL,
            timeout=10
        )

        if resposta.status_code != 200:
            return []

        dados = resposta.json()

        if isinstance(
            dados,
            list
        ):
            return dados

    except Exception:
        pass

    return []


# ============================================================
# 26. VERIFICAR DUPLICIDADE
# ============================================================

def verificar_duplicidade(
    dados,
    base
):
    titulo_novo = somente_numeros(
        dados.get(
            "titulo",
            ""
        )
    )

    cpf_novo = somente_numeros(
        dados.get(
            "cpf",
            ""
        )
    )

    for pessoa in base:
        titulo_existente = somente_numeros(
            pessoa.get(
                "titulo",
                ""
            )
        )

        cpf_existente = somente_numeros(
            pessoa.get(
                "cpf",
                ""
            )
        )

        if (
            titulo_novo
            and titulo_existente
            and titulo_novo.lstrip("0")
            == titulo_existente.lstrip("0")
        ):
            return True, pessoa

        if (
            cpf_novo
            and cpf_existente
            and cpf_novo
            == cpf_existente
        ):
            return True, pessoa

    return False, None


# ============================================================
# 27. REGRA DE DADOS MÍNIMOS
# ============================================================

def verificar_dados_minimos(
    dados
):
    faltando = []

    if not dados.get(
        "nome"
    ):
        faltando.append(
            "nome"
        )

    if not dados.get(
        "data_nascimento"
    ):
        faltando.append(
            "nascimento"
        )

    if not dados.get(
        "nome_mae"
    ):
        faltando.append(
            "nome da mãe"
        )

    if (
        not dados.get("cpf")
        and not dados.get("titulo")
    ):
        faltando.append(
            "CPF ou título"
        )

    return faltando


# ============================================================
# 28. CLASSIFICAÇÃO
# ============================================================

def classificar_resultado(
    dados,
    duplicado
):
    if duplicado:
        return "⚠️ JÁ CADASTRADO"

    faltando = verificar_dados_minimos(
        dados
    )

    if faltando:
        return (
            "❌ FALTA: "
            + ", ".join(
                faltando
            ).upper()
        )

    return "✅ COMPLETO"


# ============================================================
# 29. SUPERVISORES
# ============================================================

def obter_supervisores(
    base
):
    supervisores = []

    subs = [
        "SEM SUBSUPERVISOR"
    ]

    comunidades = []

    for item in base:
        sup = str(
            item.get(
                "supervisor",
                ""
            )
        ).strip().upper()

        sub = str(
            item.get(
                "subsupervisor",
                ""
            )
        ).strip().upper()

        comunidade = str(
            item.get(
                "comunidade",
                ""
            )
        ).strip().upper()

        if (
            sup
            and sup not in supervisores
        ):
            supervisores.append(
                sup
            )

        if (
            sub
            and sub not in subs
        ):
            subs.append(
                sub
            )

        if (
            comunidade
            and comunidade not in comunidades
        ):
            comunidades.append(
                comunidade
            )

    return (
        sorted(
            supervisores
        ),
        sorted(
            subs
        ),
        sorted(
            comunidades
        )
    )


# ============================================================
# 30. CABEÇALHO
# ============================================================

st.title(
    "📋 Sistema de Cadastro CP"
)

st.caption(
    "Leitura e conferência de documentos"
)

st.markdown(
    "---"
)


# ============================================================
# 31. CARREGAR BASE
# ============================================================

base = carregar_base()

lista_sup, lista_sub, lista_comunidade = obter_supervisores(
    base
)


# ============================================================
# 32. SIDEBAR
# ============================================================

with st.sidebar:
    st.header(
        "⚙️ Configuração"
    )

    sup_opcao = st.selectbox(
        "Supervisor",
        lista_sup
        + [
            "➕ Cadastrar Novo Supervisor"
        ]
    )

    if (
        sup_opcao
        == "➕ Cadastrar Novo Supervisor"
    ):
        supervisor = st.text_input(
            "Novo Supervisor"
        ).upper()

    else:
        supervisor = sup_opcao

    sub_opcao = st.selectbox(
        "Subsupervisor",
        lista_sub
        + [
            "➕ Cadastrar Novo Sub"
        ]
    )

    if (
        sub_opcao
        == "➕ Cadastrar Novo Sub"
    ):
        sub = st.text_input(
            "Novo Sub"
        ).upper()

    else:
        sub = sub_opcao

    comunidade_opcao = st.selectbox(
        "Comunidade",
        lista_comunidade
        + [
            "➕ Cadastrar Nova Comunidade"
        ]
    )

    if (
        comunidade_opcao
        == "➕ Cadastrar Nova Comunidade"
    ):
        comunidade = st.text_input(
            "Nova Comunidade"
        ).strip().upper()

    else:
        comunidade = comunidade_opcao

    st.markdown(
        "---"
    )

    menu = st.radio(
        "Escolha a Operação:",
        [
            "📸 Envio de Documentos",
            "✍️ Formulário Manual"
        ]
    )


# ============================================================
# 33. ENVIO DE DOCUMENTOS
# ============================================================

if menu == "📸 Envio de Documentos":

    st.subheader(
        "📁 Processamento de Documentos"
    )

    st.caption(
        f"Supervisor: {supervisor} | "
        f"Subsupervisor: {sub} | "
        f"Comunidade: {comunidade or 'NÃO INFORMADA'}"
    )

    arquivos = st.file_uploader(
        "Selecione fotos ou PDFs",
        accept_multiple_files=True,
        type=[
            "pdf",
            "jpg",
            "jpeg",
            "png"
        ]
    )

    if arquivos:
        st.info(
            f"{len(arquivos)} arquivo(s) selecionado(s). "
            "Cada documento será processado individualmente."
        )

        if st.button(
            "🔎 Processar Lote"
        ):
            resultados = []

            total = len(
                arquivos
            )

            barra = st.progress(
                0
            )

            status_area = st.empty()

            for indice, arquivo in enumerate(
                arquivos
            ):
                status_area.info(
                    f"Processando "
                    f"{indice + 1} de {total}: "
                    f"{arquivo.name}"
                )

                try:
                    texto, itens, tipo = ler_documento(
                        arquivo
                    )

                    dados = extrair_dados(
                        texto,
                        itens,
                        tipo
                    )

                    texto_tesseract = ""

                    if (
                        tipo == "Imagem — OCR"
                        and (
                            not dados.get("data_nascimento")
                            or not dados.get("nome_mae")
                            or not dados.get("nome")
                            or (
                                not dados.get("cpf")
                                and not dados.get("titulo")
                            )
                        )
                    ):
                        arquivo.seek(0)
                        imagem_fallback = Image.open(arquivo).convert("RGB")

                        texto_tesseract = executar_tesseract_imagem(
                            imagem_fallback
                        )

                        if texto_tesseract:
                            dados_tesseract = extrair_dados_tesseract(
                                texto_tesseract,
                                imagem_original=imagem_fallback
                            )

                            dados = combinar_dados_ocr(
                                dados,
                                dados_tesseract
                            )

                            candidatos_mae = (
                                dados_tesseract.get(
                                    "_candidatos_mae",
                                    []
                                )
                            )

                            if candidatos_mae:
                                dados[
                                    "_candidatos_mae"
                                ] = candidatos_mae

                        del imagem_fallback
                        gc.collect()

                        if False:
                            dados_tesseract = {}
                    # Telefone: tenta o conteúdo do documento primeiro.
                    # O nome do arquivo é apenas fallback.
                    if not dados.get("telefone"):
                        dados["telefone"] = encontrar_telefone_nome_arquivo(
                            arquivo.name
                        )

                    duplicado, existente = verificar_duplicidade(
                        dados,
                        base
                    )

                    resultado = classificar_resultado(
                        dados,
                        duplicado
                    )

                    existente_nome = ""
                    existente_sup = ""

                    if duplicado and existente:
                        existente_nome = str(
                            existente.get(
                                "nome",
                                ""
                            )
                        )

                        existente_sup = str(
                            existente.get(
                                "supervisor",
                                ""
                            )
                        )

                    resultados.append(
                        {
                            "Arquivo":
                                arquivo.name,

                            "Nome":
                                dados["nome"],

                            "CPF":
                                dados["cpf"],

                            "Título":
                                dados["titulo"],

                            "Nascimento":
                                dados[
                                    "data_nascimento"
                                ],

                            "Nome da mãe":
                                dados[
                                    "nome_mae"
                                ],

                            "Telefone":
                                dados.get(
                                    "telefone",
                                    ""
                                ),

                            "Zona":
                                dados["zona"],

                            "Seção":
                                dados["secao"],

                            "Leitura":
                                tipo,

                            "Resultado":
                                resultado,

                            "Já cadastrado como":
                                existente_nome,

                            "Supervisor atual":
                                existente_sup,

                            "_dados":
                                dados.copy(),

                            "_texto_ocr":
                                texto,

                            "_texto_tesseract":
                                texto_tesseract,

                            "_itens_ocr":
                                [
                                    {
                                        "texto": str(item.get("texto", "")),
                                        "confianca": round(float(item.get("confianca", 0)) * 100, 2),
                                        "x": round(float(item.get("x", 0)), 1),
                                        "y": round(float(item.get("y", 0)), 1)
                                    }
                                    for item in itens
                                ]
                        }
                    )

                    del texto
                    del itens

                    gc.collect()

                except Exception as erro:
                    resultados.append(
                        {
                            "Arquivo":
                                arquivo.name,

                            "Nome":
                                "",

                            "CPF":
                                "",

                            "Título":
                                "",

                            "Nascimento":
                                "",

                            "Nome da mãe":
                                "",

                            "Telefone":
                                "",

                            "Zona":
                                "",

                            "Seção":
                                "",

                            "Leitura":
                                "",

                            "Resultado":
                                "❌ ERRO",

                            "Já cadastrado como":
                                "",

                            "Supervisor atual":
                                ""
                        }
                    )

                    st.error(
                        f"Erro em "
                        f"{arquivo.name}: "
                        f"{erro}"
                    )

                barra.progress(
                    (
                        indice + 1
                    )
                    / total
                )

                gc.collect()

            status_area.success(
                "Processamento concluído."
            )

            st.session_state[
                "resultado_lote"
            ] = resultados


    # ========================================================
    # RESULTADOS
    # ========================================================

    if (
        "resultado_lote"
        in st.session_state
    ):
        resultados = st.session_state[
            "resultado_lote"
        ]

        if resultados:
            st.markdown(
                "---"
            )

            st.subheader(
                "📊 Resultado do Lote"
            )

            completos = sum(
                1
                for r in resultados
                if r["Resultado"]
                == "✅ COMPLETO"
            )

            duplicados = sum(
                1
                for r in resultados
                if r["Resultado"]
                == "⚠️ JÁ CADASTRADO"
            )

            conferir = (
                len(resultados)
                - completos
                - duplicados
            )

            col1, col2, col3 = st.columns(
                3
            )

            col1.metric(
                "Completos",
                completos
            )

            col2.metric(
                "Já cadastrados",
                duplicados
            )

            col3.metric(
                "Conferir",
                conferir
            )

            # ====================================================
            # CONFERÊNCIA / EDIÇÃO DO TELEFONE
            # ====================================================

            st.markdown("---")
            st.subheader("📞 Conferir / editar telefone")
            st.caption(
                "O telefone é opcional. Se o app encontrar no documento "
                "ou no nome do arquivo, ele já aparece preenchido. "
                "Você pode corrigir, digitar ou deixar vazio."
            )

            for indice_tel, item in enumerate(resultados):
                dados_item = item.get("_dados")

                if not dados_item:
                    continue

                if item.get("Resultado") == "⚠️ JÁ CADASTRADO":
                    continue

                chave_tel = (
                    f"telefone_{indice_tel}_"
                    f"{item.get('Arquivo', '')}"
                )

                telefone_atual = str(
                    dados_item.get("telefone", "") or ""
                )

                telefone_editado = st.text_input(
                    f"{item.get('Arquivo', 'Documento')} — "
                    f"{dados_item.get('nome', '')}",
                    value=telefone_atual,
                    key=chave_tel,
                    placeholder="Ex.: 82999999999"
                )

                if str(telefone_editado).strip():
                    telefone_limpo = normalizar_telefone(
                        telefone_editado
                    )
                else:
                    telefone_limpo = ""

                dados_item["telefone"] = telefone_limpo
                item["Telefone"] = telefone_limpo

            st.session_state[
                "resultado_lote"
            ] = resultados

            # ====================================================
            # CONFERÊNCIA MANUAL DO NOME DA MÃE
            # ====================================================

            pendentes_mae = [
                item
                for item in resultados
                if (
                    item.get("_dados")
                    and not item["_dados"].get("nome_mae")
                    and item["_dados"].get("_candidatos_mae")
                    and item.get("Resultado") != "⚠️ JÁ CADASTRADO"
                )
            ]

            if pendentes_mae:
                st.markdown("---")
                st.subheader("👩 Conferir nome da mãe")
                st.caption(
                    "O OCR encontrou nomes no documento, mas não conseguiu "
                    "determinar com segurança qual é o nome da mãe. "
                    "Selecione somente nos documentos abaixo."
                )

                houve_correcao = False

                for indice_mae, item in enumerate(pendentes_mae):
                    dados_item = item["_dados"]

                    candidatos = []

                    for candidato in dados_item.get(
                        "_candidatos_mae",
                        []
                    ):
                        candidato = str(candidato or "").strip().upper()

                        if (
                            candidato
                            and candidato != str(
                                dados_item.get("nome", "")
                            ).strip().upper()
                            and candidato not in candidatos
                        ):
                            candidatos.append(candidato)

                    if not candidatos:
                        continue

                    chave_base = (
                        f"mae_{indice_mae}_"
                        f"{item.get('Arquivo', '')}"
                    )

                    escolha = st.selectbox(
                        f"{item.get('Arquivo', 'Documento')} — "
                        f"{dados_item.get('nome', '')}",
                        options=["— SELECIONE —"] + candidatos,
                        key=chave_base
                    )

                    if escolha != "— SELECIONE —":
                        dados_item["nome_mae"] = escolha
                        item["Nome da mãe"] = escolha

                        duplicado_atual, _ = verificar_duplicidade(
                            dados_item,
                            base
                        )

                        item["Resultado"] = classificar_resultado(
                            dados_item,
                            duplicado_atual
                        )

                        houve_correcao = True

                if houve_correcao:
                    st.session_state[
                        "resultado_lote"
                    ] = resultados

            resultados_visiveis = []

            for item in resultados:
                item_visivel = {
                    chave: valor
                    for chave, valor in item.items()
                    if chave not in (
                        "_dados",
                        "_texto_ocr",
                        "_texto_tesseract",
                        "_itens_ocr",
                        "_candidatos_mae"
                    )
                }

                resultados_visiveis.append(
                    item_visivel
                )

            df_resultados = pd.DataFrame(
                resultados_visiveis
            )

            st.dataframe(
                df_resultados,
                use_container_width=True,
                hide_index=True
            )

            # ====================================================
            # SALVAR CADASTROS COMPLETOS NA TABELA
            # ====================================================

            aptos_para_salvar = [
                item
                for item in resultados
                if (
                    item.get("Resultado") == "✅ COMPLETO"
                    and item.get("_dados")
                )
            ]

            if aptos_para_salvar:

                st.markdown("---")

                st.info(
                    f"📥 {len(aptos_para_salvar)} cadastro(s) "
                    f"completo(s) pronto(s) para salvar."
                )

                if st.button(
                    "💾 Salvar completos na TABELA",
                    type="primary"
                ):
                    salvos = 0
                    duplicados_salvar = 0
                    erros_salvar = 0

                    progresso_salvar = st.progress(0)

                    for indice_salvar, item in enumerate(
                        aptos_para_salvar
                    ):
                        dados_salvar = dict(
                            item["_dados"]
                        )

                        dados_salvar.pop(
                            "_candidatos_mae",
                            None
                        )

                        dados_salvar[
                            "comunidade"
                        ] = comunidade

                        retorno = sheets.salvar_cadastro(
                            WEBHOOK_URL,
                            dados_salvar,
                            supervisor,
                            sub,
                            dados_base=base
                        )

                        status_salvar = retorno.get(
                            "status",
                            "ERRO"
                        )

                        if status_salvar == "SUCESSO":
                            salvos += 1

                        elif status_salvar == "DUPLICADO":
                            duplicados_salvar += 1

                        else:
                            erros_salvar += 1

                            st.error(
                                f"{item['Arquivo']}: "
                                f"{retorno.get('mensagem', 'Erro ao salvar.')}"
                            )

                        progresso_salvar.progress(
                            (indice_salvar + 1)
                            / len(aptos_para_salvar)
                        )

                    st.success(
                        f"Salvamento concluído: "
                        f"{salvos} salvo(s), "
                        f"{duplicados_salvar} duplicado(s) "
                        f"e {erros_salvar} erro(s)."
                    )

                    st.cache_data.clear()

            st.caption(
                "ℹ️ Para ser considerado completo: "
                "Nome + Nascimento + Nome da mãe + "
                "CPF ou Título. "
                "Nenhum cadastro do lote foi gravado "
                "automaticamente."
            )

            # ====================================================
            # DIAGNÓSTICO TEMPORÁRIO DO OCR
            # ====================================================
            st.markdown("---")
            st.subheader("🛠️ Diagnóstico OCR")

            st.caption(
                "Área temporária para conferir exatamente o que "
                "o OCR reconheceu. Não altera nem salva cadastros."
            )

            for indice_diag, item_diag in enumerate(resultados):
                texto_diag = str(
                    item_diag.get("_texto_ocr", "") or ""
                ).strip()

                itens_diag = item_diag.get(
                    "_itens_ocr",
                    []
                )

                with st.expander(
                    f"🔎 {item_diag.get('Arquivo', 'Documento')}",
                    expanded=False
                ):
                    st.markdown("**Texto reconhecido:**")

                    if texto_diag:
                        st.code(
                            texto_diag,
                            language=None
                        )
                    else:
                        st.warning(
                            "Nenhum texto bruto foi retornado."
                        )

                    texto_tess_diag = str(
                        item_diag.get("_texto_tesseract", "") or ""
                    ).strip()

                    if texto_tess_diag:
                        st.markdown(
                            "**Texto reconhecido pelo Tesseract (fallback):**"
                        )
                        st.code(
                            texto_tess_diag,
                            language=None
                        )

                    st.markdown("**Blocos reconhecidos pelo OCR:**")

                    if itens_diag:
                        df_diag = pd.DataFrame(
                            itens_diag
                        )

                        st.dataframe(
                            df_diag,
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.info(
                            "Este arquivo não possui blocos OCR. "
                            "Se for PDF com texto digital, isso é esperado."
                        )


# ============================================================
# 34. FORMULÁRIO MANUAL
# ============================================================

elif menu == "✍️ Formulário Manual":

    st.subheader(
        "✍️ Consulta & Cadastro Manual"
    )

    if (
        "busca_realizada"
        not in st.session_state
    ):
        st.session_state.update(
            {
                "busca_realizada":
                    False,

                "titulo":
                    "",

                "encontrado":
                    None
            }
        )

    titulo_input = st.text_input(
        "Título de Eleitor:",
        value=st.session_state.titulo
    )

    if st.button(
        "🔍 Pesquisar"
    ):
        st.session_state.titulo = (
            titulo_input
        )

        titulo_pesquisado = somente_numeros(
            titulo_input
        ).lstrip(
            "0"
        )

        encontrado = None

        for pessoa in base:
            titulo_base = somente_numeros(
                pessoa.get(
                    "titulo",
                    ""
                )
            ).lstrip(
                "0"
            )

            if (
                titulo_pesquisado
                and titulo_base
                == titulo_pesquisado
            ):
                encontrado = pessoa
                break

        st.session_state.encontrado = (
            encontrado
        )

        st.session_state.busca_realizada = (
            True
        )

    if st.session_state.busca_realizada:

        if st.session_state.encontrado:
            e = st.session_state.encontrado

            st.error(
                f"⚠️ Já cadastrado: "
                f"{e.get('nome')} | "
                f"Supervisor: "
                f"{e.get('supervisor')}"
            )

            if st.button(
                "Limpar"
            ):
                st.session_state.busca_realizada = (
                    False
                )

                st.session_state.encontrado = (
                    None
                )

                st.session_state.titulo = ""

                st.rerun()

        else:
            st.success(
                "Título não localizado na base. "
                "O cadastro pode ser realizado."
            )

            with st.form(
                "cadastro_manual"
            ):
                nome = st.text_input(
                    "Nome *"
                )

                cpf = st.text_input(
                    "CPF"
                )

                data_nasc = st.text_input(
                    "Data de Nascimento "
                    "(DD/MM/AAAA)"
                )

                nome_mae = st.text_input(
                    "Nome da mãe"
                )

                salvar = st.form_submit_button(
                    "💾 Salvar"
                )

                if salvar:
                    if not nome:
                        st.error(
                            "Informe o nome."
                        )

                    else:
                        payload = {
                            "titulo":
                                st.session_state.titulo,

                            "nome":
                                nome,

                            "cpf":
                                cpf,

                            "data_nascimento":
                                data_nasc,

                            "nome_mae":
                                nome_mae,

                            "supervisor":
                                supervisor,

                            "subsupervisor":
                                sub,

                            "comunidade":
                                comunidade
                        }

                        try:
                            resposta = requests.post(
                                WEBHOOK_URL,
                                json=payload,
                                timeout=30
                            )

                            resultado = resposta.json()

                            if (
                                resultado.get(
                                    "status"
                                )
                                == "SUCESSO"
                            ):
                                st.success(
                                    "Salvo com sucesso!"
                                )

                                st.cache_data.clear()

                                st.session_state.busca_realizada = (
                                    False
                                )

                                st.session_state.encontrado = (
                                    None
                                )

                                st.session_state.titulo = ""

                                st.rerun()

                            else:
                                st.error(
                                    resultado.get(
                                        "mensagem",
                                        "Erro ao salvar."
                                    )
                                )

                        except Exception as erro:
                            st.error(
                                f"Erro ao salvar: {erro}"
                            )
