import streamlit as st
import streamlit.components.v1 as components
import requests
import re
import io
import base64
import gc
import unicodedata
import numpy as np
import pandas as pd
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import pytesseract
import fitz
import sheets
import cruzamento
import relatorios
from validacoes import (
    somente_numeros,
    normalizar_texto,
    remover_acentos,
    normalizar_rotulo,
    formatar_cpf,
    cpf_valido,
    data_valida,
)

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



@st.cache_data(ttl=60)
def carregar_bases_concorrentes():
    """
    Carrega a aba CONCORRENTE uma vez por ciclo de cache.
    Se houver falha, devolve o erro sem impedir o cadastro.
    """
    return cruzamento.carregar_bases(
        WEBHOOK_URL
    )


def consultar_bases_titulo(titulo):
    """
    Cruza o título com as bases já carregadas.
    Retorna somente as bases onde foi encontrado.
    """
    titulo = somente_numeros(
        titulo
    )

    if not titulo:
        return {
            "sucesso": True,
            "encontrado": False,
            "bases": [],
            "texto": "",
            "mensagem": ""
        }

    consulta = carregar_bases_concorrentes()

    if not consulta.get("sucesso"):
        return {
            "sucesso": False,
            "encontrado": False,
            "bases": [],
            "texto": "",
            "mensagem": consulta.get(
                "mensagem",
                "Erro ao consultar CONCORRENTE."
            )
        }

    resultado = cruzamento.cruzar_titulo(
        titulo,
        consulta.get("bases", {})
    )

    return {
        "sucesso": True,
        "encontrado": resultado.get(
            "encontrado",
            False
        ),
        "bases": resultado.get(
            "bases",
            []
        ),
        "texto": resultado.get(
            "texto",
            ""
        ),
        "mensagem": ""
    }


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
        "⚙️ Menu"
    )

    menu = st.radio(
        "Escolha a Operação:",
        [
            "📸 Envio de Documentos",
            "✍️ Formulário Manual",
            "📊 Relatórios"
        ]
    )

    supervisor = ""
    sub = ""
    comunidade = ""

    if menu != "📊 Relatórios":
        st.markdown(
            "---"
        )

        st.subheader(
            "Configuração do cadastro"
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

    if "lote_upload_id" not in st.session_state:
        st.session_state["lote_upload_id"] = 0

    arquivos = st.file_uploader(
        "Selecione fotos ou PDFs",
        accept_multiple_files=True,
        type=[
            "pdf",
            "jpg",
            "jpeg",
            "png"
        ],
        key=f"arquivos_lote_{st.session_state['lote_upload_id']}"
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

                    # Cruza automaticamente o título com a aba CONCORRENTE.
                    cruzamento_item = consultar_bases_titulo(
                        dados.get("titulo", "")
                    )

                    bases_encontradas = (
                        cruzamento_item.get("texto", "")
                        if cruzamento_item.get("sucesso")
                        else ""
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

                            "Bases encontradas":
                                bases_encontradas,

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

                            "Bases encontradas":
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

            # ====================================================
            # RESULTADO COMPACTO / CONFERÊNCIA NA PRÓPRIA LINHA
            # ====================================================

            st.markdown(
                f"""
                <div style="
                    background:#ffffff;
                    border:1px solid #d9e1e8;
                    border-radius:10px;
                    padding:10px 14px;
                    margin:4px 0 12px 0;
                    font-size:0.95rem;
                ">
                    <b>📊 Resultado do lote</b>
                    &nbsp;&nbsp; ✅ {completos} completos
                    &nbsp;&nbsp; 🔁 {duplicados} já cadastrados
                    &nbsp;&nbsp; ⚠️ {conferir} conferir
                </div>
                """,
                unsafe_allow_html=True
            )

            st.caption(
                "Confira os dados abaixo. Se o OCR errar algum campo, "
                "corrija diretamente antes de salvar."
            )

            for indice_item, item in enumerate(resultados):
                dados_item = item.get("_dados")

                if not dados_item:
                    st.error(
                        f"{item.get('Arquivo', 'Documento')} — "
                        f"{item.get('Resultado', '❌ ERRO')}"
                    )
                    continue

                arquivo_item = str(
                    item.get("Arquivo", "Documento") or "Documento"
                ).strip()

                prefixo_chave = (
                    f"edicao_{indice_item}_"
                    f"{re.sub(r'[^A-Za-z0-9]+', '_', arquivo_item)}"
                )

                # ------------------------------------------------
                # CAMPOS EDITÁVEIS DO OCR
                # ------------------------------------------------
                # A leitura automática continua sendo o ponto de partida.
                # O operador corrige somente as exceções.
                col_nome, col_nasc = st.columns([2.2, 1])

                with col_nome:
                    nome_editado = st.text_input(
                        "Nome",
                        value=str(
                            dados_item.get("nome", "") or ""
                        ).strip(),
                        key=f"{prefixo_chave}_nome"
                    )

                with col_nasc:
                    nascimento_editado = st.text_input(
                        "Nascimento",
                        value=str(
                            dados_item.get(
                                "data_nascimento",
                                ""
                            ) or ""
                        ).strip(),
                        key=f"{prefixo_chave}_nascimento",
                        placeholder="DD/MM/AAAA"
                    )

                col_cpf, col_titulo, col_zona, col_secao = st.columns(
                    [1.25, 1.35, 0.65, 0.65]
                )

                with col_cpf:
                    cpf_editado = st.text_input(
                        "CPF",
                        value=str(
                            dados_item.get("cpf", "") or ""
                        ).strip(),
                        key=f"{prefixo_chave}_cpf"
                    )

                with col_titulo:
                    titulo_editado = st.text_input(
                        "Título",
                        value=str(
                            dados_item.get("titulo", "") or ""
                        ).strip(),
                        key=f"{prefixo_chave}_titulo"
                    )

                with col_zona:
                    zona_editada = st.text_input(
                        "Zona",
                        value=str(
                            dados_item.get("zona", "") or ""
                        ).strip(),
                        key=f"{prefixo_chave}_zona"
                    )

                with col_secao:
                    secao_editada = st.text_input(
                        "Seção",
                        value=str(
                            dados_item.get("secao", "") or ""
                        ).strip(),
                        key=f"{prefixo_chave}_secao"
                    )

                # Atualiza os dados usados pelo restante do sistema.
                dados_item["nome"] = str(
                    nome_editado or ""
                ).strip().upper()

                dados_item["data_nascimento"] = str(
                    nascimento_editado or ""
                ).strip()

                dados_item["cpf"] = somente_numeros(
                    cpf_editado
                )

                dados_item["titulo"] = somente_numeros(
                    titulo_editado
                )

                dados_item["zona"] = somente_numeros(
                    zona_editada
                )

                dados_item["secao"] = somente_numeros(
                    secao_editada
                )

                # ------------------------------------------------
                # NOME DA MÃE + TELEFONE
                # ------------------------------------------------
                nome_item = str(
                    dados_item.get("nome", "")
                    or "NOME NÃO IDENTIFICADO"
                ).strip()

                col_mae, col_tel = st.columns([2.2, 1])

                with col_mae:
                    mae_atual = str(
                        dados_item.get("nome_mae", "") or ""
                    ).strip().upper()

                    candidatos = []

                    for candidato in dados_item.get(
                        "_candidatos_mae",
                        []
                    ):
                        candidato = str(
                            candidato or ""
                        ).strip().upper()

                        candidato_norm = normalizar_rotulo(
                            candidato
                        )
                        nome_norm = normalizar_rotulo(
                            nome_item
                        )

                        eh_fragmento_nome = (
                            candidato_norm
                            and nome_norm
                            and (
                                candidato_norm in nome_norm
                                or nome_norm in candidato_norm
                            )
                        )

                        if (
                            candidato
                            and not eh_fragmento_nome
                            and candidato not in candidatos
                        ):
                            candidatos.append(candidato)

                    chave_mae = f"{prefixo_chave}_mae"
                    chave_sugestao = f"{prefixo_chave}_sugestao_mae"

                    # O nome da mãe é SEMPRE um campo livre/editável.
                    # Sugestões do OCR nunca bloqueiam a digitação.
                    if chave_mae not in st.session_state:
                        st.session_state[chave_mae] = mae_atual

                    # Se houver sugestão, ela é opcional e apenas preenche
                    # o campo livre quando o usuário escolher.
                    if candidatos:
                        sugestao_mae = st.selectbox(
                            "Sugestão do OCR (opcional)",
                            options=["— IGNORAR —"] + candidatos,
                            key=chave_sugestao
                        )

                        if (
                            sugestao_mae != "— IGNORAR —"
                            and st.session_state.get(chave_mae, "") != sugestao_mae
                        ):
                            st.session_state[chave_mae] = sugestao_mae

                    mae_editada = st.text_input(
                        "Nome da mãe",
                        key=chave_mae,
                        placeholder="Digite o nome da mãe"
                    )

                    dados_item["nome_mae"] = str(
                        mae_editada or ""
                    ).strip().upper()

                    item["Nome da mãe"] = dados_item["nome_mae"]

                with col_tel:
                    telefone_editado = st.text_input(
                        "Telefone",
                        value=str(
                            dados_item.get("telefone", "") or ""
                        ),
                        key=f"{prefixo_chave}_telefone",
                        placeholder="82999999999"
                    )

                    dados_item["telefone"] = normalizar_telefone(
                        telefone_editado
                    ) if str(telefone_editado).strip() else ""

                    item["Telefone"] = dados_item["telefone"]

                # ------------------------------------------------
                # RECALCULAR DUPLICIDADE + CRUZAMENTO + STATUS
                # ------------------------------------------------
                duplicado_atual, existente_atual = verificar_duplicidade(
                    dados_item,
                    base
                )

                resultado_cruzamento = consultar_bases_titulo(
                    dados_item.get("titulo", "")
                )

                if resultado_cruzamento.get("sucesso"):
                    bases_item = str(
                        resultado_cruzamento.get("texto", "") or ""
                    ).strip()
                else:
                    bases_item = ""

                item["Bases encontradas"] = bases_item

                if duplicado_atual:
                    item["Resultado"] = "⚠️ JÁ CADASTRADO"
                    item["Já cadastrado como"] = str(
                        (existente_atual or {}).get("nome", "") or ""
                    )
                    item["Supervisor atual"] = str(
                        (existente_atual or {}).get(
                            "supervisor",
                            ""
                        ) or ""
                    )
                else:
                    item["Resultado"] = classificar_resultado(
                        dados_item,
                        False
                    )
                    item["Já cadastrado como"] = ""
                    item["Supervisor atual"] = ""

                # Espelha os valores editados no item.
                item["Nome"] = dados_item.get("nome", "")
                item["CPF"] = dados_item.get("cpf", "")
                item["Título"] = dados_item.get("titulo", "")
                item["Nascimento"] = dados_item.get(
                    "data_nascimento",
                    ""
                )
                item["Zona"] = dados_item.get("zona", "")
                item["Seção"] = dados_item.get("secao", "")

                # ------------------------------------------------
                # RESULTADO SINTÉTICO DEPOIS DAS CORREÇÕES
                # ------------------------------------------------
                resumo = f"**{nome_item}**  ·  {item['Resultado']}"

                if bases_item:
                    resumo += f"  ·  🎯 Base: **{bases_item}**"

                resumo += f"  ·  📄 {arquivo_item}"

                st.markdown(resumo)

                if item.get("Resultado") == "⚠️ JÁ CADASTRADO":
                    detalhes_duplicado = []

                    if item.get("Já cadastrado como"):
                        detalhes_duplicado.append(
                            "já cadastrado como "
                            + item["Já cadastrado como"]
                        )

                    if item.get("Supervisor atual"):
                        detalhes_duplicado.append(
                            "supervisor atual: "
                            + item["Supervisor atual"]
                        )

                    if detalhes_duplicado:
                        st.caption(
                            "↳ " + " • ".join(detalhes_duplicado)
                        )

                st.markdown(
                    "<div style='border-bottom:1px solid #d9e1e8; "
                    "margin:4px 0 10px 0;'></div>",
                    unsafe_allow_html=True
                )

            st.session_state[
                "resultado_lote"
            ] = resultados

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
                "ℹ️ Completo = Nome + Nascimento + Nome da mãe + "
                "CPF ou Título. Nenhum cadastro é gravado automaticamente."
            )

            if st.button(
                "🧹 Finalizar lote / Novo lote",
                use_container_width=True
            ):
                st.session_state.pop("resultado_lote", None)

                # Remove apenas estados temporários dos campos do lote atual.
                for chave in list(st.session_state.keys()):
                    if (
                        str(chave).startswith("mae_compacta_")
                        or str(chave).startswith("telefone_compacto_")
                    ):
                        del st.session_state[chave]

                # Trocar a chave do uploader faz o Streamlit limpar
                # todos os arquivos selecionados de uma vez.
                st.session_state["lote_upload_id"] += 1
                st.rerun()


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
                    None,

                "bases_concorrentes":
                    "",

                "erro_concorrentes":
                    ""
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

        resultado_cruzamento = consultar_bases_titulo(
            titulo_input
        )

        if resultado_cruzamento.get("sucesso"):
            st.session_state.bases_concorrentes = (
                resultado_cruzamento.get("texto", "")
            )
            st.session_state.erro_concorrentes = ""
        else:
            st.session_state.bases_concorrentes = ""
            st.session_state.erro_concorrentes = (
                resultado_cruzamento.get("mensagem", "")
            )

        st.session_state.busca_realizada = (
            True
        )

    if st.session_state.busca_realizada:

        if st.session_state.bases_concorrentes:
            st.warning(
                "Encontrado nas bases: "
                f"{st.session_state.bases_concorrentes}"
            )

        if st.session_state.erro_concorrentes:
            st.warning(
                "Não foi possível consultar a aba CONCORRENTE: "
                f"{st.session_state.erro_concorrentes}"
            )

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
                st.session_state.bases_concorrentes = ""
                st.session_state.erro_concorrentes = ""

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
                                st.session_state.bases_concorrentes = ""
                                st.session_state.erro_concorrentes = ""

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


# ============================================================
# 35. RELATÓRIOS
# ============================================================

elif menu == "📊 Relatórios":

    st.subheader("📊 Relatórios")
    st.caption("Consulte a base cadastrada de forma rápida e organizada.")

    tipo_relatorio = st.selectbox(
        "Tipo de relatório",
        [
            "👤 Por Nome",
            "📍 Por Zona",
            "🏠 Por Domicílio",
            "🔀 Cruzamentos"
        ],
        key="tipo_relatorio"
    )

    # ========================================================
    # RELATÓRIO POR NOME
    # ========================================================

    if tipo_relatorio == "👤 Por Nome":

        filtros_disponiveis = relatorios.obter_filtros_nome(base)

        col_filtro_sup, col_filtro_sub, col_filtro_sit = st.columns(3)

        with col_filtro_sup:
            filtro_supervisor = st.selectbox(
                "Supervisor",
                ["Todos"] + filtros_disponiveis.get("supervisores", []),
                key="relatorio_nome_supervisor"
            )

        with col_filtro_sub:
            filtro_subsupervisor = st.selectbox(
                "Subsupervisor",
                ["Todos"] + filtros_disponiveis.get("subsupervisores", []),
                key="relatorio_nome_subsupervisor"
            )

        with col_filtro_sit:
            filtro_situacao = st.selectbox(
                "Situação",
                ["Todas"] + filtros_disponiveis.get("situacoes", []),
                key="relatorio_nome_situacao"
            )

        gerar_relatorio = st.button(
            "🔎 Gerar relatório",
            type="primary",
            use_container_width=True,
            key="gerar_relatorio_nome"
        )

        if gerar_relatorio:
            st.session_state["relatorio_nome_gerado"] = (
                relatorios.gerar_relatorio_nome(
                    dados_base=base,
                    supervisor=(
                        "" if filtro_supervisor == "Todos"
                        else filtro_supervisor
                    ),
                    subsupervisor=(
                        "" if filtro_subsupervisor == "Todos"
                        else filtro_subsupervisor
                    ),
                    situacao=(
                        "" if filtro_situacao == "Todas"
                        else filtro_situacao
                    )
                )
            )

        resultado_relatorio = st.session_state.get("relatorio_nome_gerado")

        if resultado_relatorio is not None:

            total_relatorio = resultado_relatorio.get("total", 0)

            st.markdown(
                f"""
                <div style="
                    background:#ffffff;
                    border:1px solid #d9e1e8;
                    border-radius:10px;
                    padding:10px 14px;
                    margin:14px 0 12px 0;
                    font-size:0.95rem;
                ">
                    <b>👤 Relatório por Nome</b>
                    &nbsp;&nbsp; <b>{total_relatorio}</b> registro(s)
                </div>
                """,
                unsafe_allow_html=True
            )

            if total_relatorio == 0:
                st.info(
                    "Nenhum cadastro encontrado para os filtros selecionados."
                )

            else:
                for numero_grupo, grupo in enumerate(
                    resultado_relatorio.get("grupos", []),
                    start=1
                ):
                    nome_supervisor = str(
                        grupo.get("supervisor", "SEM SUPERVISOR")
                    ).strip()

                    nome_subsupervisor = str(
                        grupo.get("subsupervisor", "SEM SUBSUPERVISOR")
                    ).strip()

                    registros_grupo = grupo.get("registros", [])

                    st.markdown(
                        f"""
                        <div style="
                            background:#f7f9fb;
                            border-left:4px solid #0056b3;
                            padding:8px 12px;
                            margin-top:12px;
                            margin-bottom:6px;
                            border-radius:6px;
                        ">
                            <b>Supervisor:</b> {nome_supervisor}
                            &nbsp;&nbsp;&nbsp;
                            <b>Subsupervisor:</b> {nome_subsupervisor}
                            &nbsp;&nbsp;&nbsp;
                            <b>Total:</b> {len(registros_grupo)}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    linhas_tabela = []

                    for numero, registro in enumerate(
                        registros_grupo,
                        start=1
                    ):
                        linhas_tabela.append(
                            {
                                "Nº": numero,
                                "Nome": str(
                                    registro.get("nome", "")
                                ).strip(),
                                "Comunidade": str(
                                    registro.get("comunidade", "")
                                ).strip(),
                                "Telefone": str(
                                    registro.get("telefone", "")
                                ).strip()
                            }
                        )

                    tabela_grupo = pd.DataFrame(linhas_tabela)

                    st.dataframe(
                        tabela_grupo,
                        use_container_width=True,
                        hide_index=True,
                        height=min(
                            38 * len(tabela_grupo) + 38,
                            500
                        )
                    )

            if total_relatorio > 0:
                try:
                    pdf_relatorio = relatorios.gerar_pdf_relatorio_nome(
                        resultado_relatorio
                    )

                    coluna_imprimir, coluna_pdf = st.columns(2)

                    with coluna_imprimir:
                        pdf_base64 = base64.b64encode(
                            pdf_relatorio
                        ).decode("utf-8")

                        components.html(
                            f"""
                            <button onclick="imprimirPDFNome()" style="
                                width: 100%;
                                height: 38px;
                                background: #0056b3;
                                color: white;
                                border: 2px solid #0056b3;
                                border-radius: 12px;
                                font-weight: bold;
                                cursor: pointer;
                                font-family: sans-serif;
                            ">🖨️ Imprimir</button>

                            <script>
                            function imprimirPDFNome() {{
                                const base64 = "{pdf_base64}";
                                const binario = atob(base64);
                                const bytes = new Uint8Array(binario.length);

                                for (let i = 0; i < binario.length; i++) {{
                                    bytes[i] = binario.charCodeAt(i);
                                }}

                                const blob = new Blob(
                                    [bytes],
                                    {{type: "application/pdf"}}
                                );

                                const url = URL.createObjectURL(blob);
                                const janela = window.open(
                                    url,
                                    "_blank",
                                    "width=1000,height=800"
                                );

                                if (!janela) {{
                                    alert(
                                        "O navegador bloqueou o pop-up. "
                                        + "Permita pop-ups para este site."
                                    );
                                    return;
                                }}

                                setTimeout(function() {{
                                    try {{
                                        janela.focus();
                                        janela.print();
                                    }} catch (e) {{
                                    }}
                                }}, 1200);
                            }}
                            </script>
                            """,
                            height=45,
                            scrolling=False
                        )

                    with coluna_pdf:
                        st.download_button(
                            label="📄 Baixar PDF",
                            data=pdf_relatorio,
                            file_name="relatorio_por_nome.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key="baixar_pdf_relatorio_nome"
                        )

                except Exception as erro_pdf:
                    st.error(
                        f"Não foi possível gerar o PDF: {erro_pdf}"
                    )

    # ========================================================
    # RELATÓRIO POR ZONA
    # ========================================================

    elif tipo_relatorio == "📍 Por Zona":

        filtros_disponiveis = relatorios.obter_filtros_zona(base)

        col_sup, col_sub, col_sit = st.columns(3)

        with col_sup:
            filtro_supervisor = st.selectbox(
                "Supervisor",
                ["Todos"] + filtros_disponiveis.get("supervisores", []),
                key="relatorio_zona_supervisor"
            )

        with col_sub:
            filtro_subsupervisor = st.selectbox(
                "Subsupervisor",
                ["Todos"] + filtros_disponiveis.get("subsupervisores", []),
                key="relatorio_zona_subsupervisor"
            )

        with col_sit:
            filtro_situacao = st.selectbox(
                "Situação",
                ["Todas"] + filtros_disponiveis.get("situacoes", []),
                key="relatorio_zona_situacao"
            )

        col_zona, col_secao = st.columns(2)

        with col_zona:
            filtro_zona = st.selectbox(
                "Zona",
                ["Todas"] + filtros_disponiveis.get("zonas", []),
                key="relatorio_zona_zona"
            )

        secoes_disponiveis = relatorios.obter_secoes_por_zona(
            base,
            "" if filtro_zona == "Todas" else filtro_zona
        )

        with col_secao:
            filtro_secao = st.selectbox(
                "Seção",
                ["Todas"] + secoes_disponiveis,
                key="relatorio_zona_secao"
            )

        gerar_relatorio_zona = st.button(
            "🔎 Gerar relatório",
            type="primary",
            use_container_width=True,
            key="gerar_relatorio_zona"
        )

        if gerar_relatorio_zona:
            st.session_state["relatorio_zona_gerado"] = (
                relatorios.gerar_relatorio_zona(
                    dados_base=base,
                    supervisor=(
                        "" if filtro_supervisor == "Todos"
                        else filtro_supervisor
                    ),
                    subsupervisor=(
                        "" if filtro_subsupervisor == "Todos"
                        else filtro_subsupervisor
                    ),
                    zona=(
                        "" if filtro_zona == "Todas"
                        else filtro_zona
                    ),
                    secao=(
                        "" if filtro_secao == "Todas"
                        else filtro_secao
                    ),
                    situacao=(
                        "" if filtro_situacao == "Todas"
                        else filtro_situacao
                    )
                )
            )

        resultado_zona = st.session_state.get("relatorio_zona_gerado")

        if resultado_zona is not None:

            total = resultado_zona.get("total", 0)
            total_zonas = resultado_zona.get("total_zonas", 0)
            total_secoes = resultado_zona.get("total_secoes", 0)

            st.markdown(
                f"""
                <div style="
                    background:#ffffff;
                    border:1px solid #d9e1e8;
                    border-radius:10px;
                    padding:10px 14px;
                    margin:14px 0 12px 0;
                    font-size:0.95rem;
                ">
                    <b>📍 Relatório por Zona</b>
                    &nbsp;&nbsp; <b>{total}</b> registro(s)
                    &nbsp;&nbsp; <b>{total_zonas}</b> zona(s)
                    &nbsp;&nbsp; <b>{total_secoes}</b> seção(ões)
                </div>
                """,
                unsafe_allow_html=True
            )

            if total == 0:
                st.info(
                    "Nenhum cadastro encontrado para os filtros selecionados."
                )

            else:
                linhas = []

                for numero, registro in enumerate(
                    resultado_zona.get("registros", []),
                    start=1
                ):
                    linhas.append(
                        {
                            "Nº": numero,
                            "Zona": registro.get("zona", ""),
                            "Seção": registro.get("secao", ""),
                            "Nome": registro.get("nome", ""),
                            "Comunidade": registro.get("comunidade", ""),
                            "Telefone": registro.get("telefone", "")
                        }
                    )

                tabela_zona = pd.DataFrame(linhas)

                st.dataframe(
                    tabela_zona,
                    use_container_width=True,
                    hide_index=True,
                    height=min(
                        38 * len(tabela_zona) + 38,
                        600
                    )
                )

                st.markdown("#### Resumo por Zona e Seção")

                resumo_linhas = []

                for grupo in resultado_zona.get("resumo", []):
                    zona_atual = grupo.get("zona", "")

                    for item in grupo.get("secoes", []):
                        resumo_linhas.append(
                            {
                                "Zona": zona_atual,
                                "Seção": item.get("secao", ""),
                                "Quantidade": item.get("total", 0)
                            }
                        )

                    resumo_linhas.append(
                        {
                            "Zona": f"TOTAL ZONA {zona_atual}",
                            "Seção": "",
                            "Quantidade": grupo.get("total", 0)
                        }
                    )

                resumo_linhas.append(
                    {
                        "Zona": "TOTAL GERAL",
                        "Seção": "",
                        "Quantidade": total
                    }
                )

                st.dataframe(
                    pd.DataFrame(resumo_linhas),
                    use_container_width=True,
                    hide_index=True
                )

                try:
                    pdf_relatorio_zona = (
                        relatorios.gerar_pdf_relatorio_zona(
                            resultado_zona
                        )
                    )

                    coluna_imprimir, coluna_pdf = st.columns(2)

                    with coluna_imprimir:
                        pdf_base64_zona = base64.b64encode(
                            pdf_relatorio_zona
                        ).decode("utf-8")

                        components.html(
                            f"""
                            <button onclick="imprimirPDFZona()" style="
                                width: 100%;
                                height: 38px;
                                background: #0056b3;
                                color: white;
                                border: 2px solid #0056b3;
                                border-radius: 12px;
                                font-weight: bold;
                                cursor: pointer;
                                font-family: sans-serif;
                            ">🖨️ Imprimir</button>

                            <script>
                            function imprimirPDFZona() {{
                                const base64 = "{pdf_base64_zona}";
                                const binario = atob(base64);
                                const bytes = new Uint8Array(binario.length);

                                for (let i = 0; i < binario.length; i++) {{
                                    bytes[i] = binario.charCodeAt(i);
                                }}

                                const blob = new Blob(
                                    [bytes],
                                    {{type: "application/pdf"}}
                                );

                                const url = URL.createObjectURL(blob);
                                const janela = window.open(
                                    url,
                                    "_blank",
                                    "width=1000,height=800"
                                );

                                if (!janela) {{
                                    alert(
                                        "O navegador bloqueou o pop-up. "
                                        + "Permita pop-ups para este site."
                                    );
                                    return;
                                }}

                                setTimeout(function() {{
                                    try {{
                                        janela.focus();
                                        janela.print();
                                    }} catch (e) {{
                                    }}
                                }}, 1200);
                            }}
                            </script>
                            """,
                            height=45,
                            scrolling=False
                        )

                    with coluna_pdf:
                        st.download_button(
                            label="📄 Baixar PDF",
                            data=pdf_relatorio_zona,
                            file_name="relatorio_por_zona.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key="baixar_pdf_relatorio_zona"
                        )

                except Exception as erro_pdf:
                    st.error(
                        f"Não foi possível gerar o PDF: {erro_pdf}"
                    )

    # ========================================================
    # RELATÓRIO POR DOMICÍLIO
    # ========================================================

    elif tipo_relatorio == "🏠 Por Domicílio":

        filtros_disponiveis = relatorios.obter_filtros_domicilio(base)

        col_sup, col_sub = st.columns(2)

        with col_sup:
            filtro_supervisor = st.selectbox(
                "Supervisor",
                ["Todos"] + filtros_disponiveis.get("supervisores", []),
                key="relatorio_domicilio_supervisor"
            )

        with col_sub:
            filtro_subsupervisor = st.selectbox(
                "Subsupervisor",
                ["Todos"] + filtros_disponiveis.get("subsupervisores", []),
                key="relatorio_domicilio_subsupervisor"
            )

        col_dom, col_sit = st.columns(2)

        with col_dom:
            filtro_domicilio = st.selectbox(
                "Domicílio",
                ["Todos"] + filtros_disponiveis.get("domicilios", []),
                key="relatorio_domicilio_domicilio"
            )

        with col_sit:
            filtro_situacao = st.selectbox(
                "Situação",
                ["Todas"] + filtros_disponiveis.get("situacoes", []),
                key="relatorio_domicilio_situacao"
            )

        gerar_relatorio_domicilio = st.button(
            "🔎 Gerar relatório",
            type="primary",
            use_container_width=True,
            key="gerar_relatorio_domicilio"
        )

        if gerar_relatorio_domicilio:
            st.session_state["relatorio_domicilio_gerado"] = (
                relatorios.gerar_relatorio_domicilio(
                    dados_base=base,
                    supervisor=(
                        "" if filtro_supervisor == "Todos"
                        else filtro_supervisor
                    ),
                    subsupervisor=(
                        "" if filtro_subsupervisor == "Todos"
                        else filtro_subsupervisor
                    ),
                    domicilio=(
                        "" if filtro_domicilio == "Todos"
                        else filtro_domicilio
                    ),
                    situacao=(
                        "" if filtro_situacao == "Todas"
                        else filtro_situacao
                    )
                )
            )

        resultado_domicilio = st.session_state.get(
            "relatorio_domicilio_gerado"
        )

        if resultado_domicilio is not None:
            total = resultado_domicilio.get("total", 0)
            total_domicilios = resultado_domicilio.get("total_domicilios", 0)

            st.markdown(
                f"""
                <div style="
                    background:#ffffff;
                    border:1px solid #d9e1e8;
                    border-radius:10px;
                    padding:10px 14px;
                    margin:14px 0 12px 0;
                    font-size:0.95rem;
                ">
                    <b>🏠 Relatório por Domicílio</b>
                    &nbsp;&nbsp; <b>{total}</b> registro(s)
                    &nbsp;&nbsp; <b>{total_domicilios}</b> domicílio(s)
                </div>
                """,
                unsafe_allow_html=True
            )

            if total == 0:
                st.info(
                    "Nenhum cadastro encontrado para os filtros selecionados."
                )

            else:
                linhas = []

                for numero, registro in enumerate(
                    resultado_domicilio.get("registros", []),
                    start=1
                ):
                    linhas.append(
                        {
                            "Nº": numero,
                            "Domicílio": registro.get("domicilio", ""),
                            "Nome": registro.get("nome", ""),
                            "Comunidade": registro.get("comunidade", ""),
                            "Telefone": registro.get("telefone", "")
                        }
                    )

                tabela_domicilio = pd.DataFrame(linhas)

                st.dataframe(
                    tabela_domicilio,
                    use_container_width=True,
                    hide_index=True,
                    height=min(
                        38 * len(tabela_domicilio) + 38,
                        600
                    )
                )

                st.markdown("#### Resumo por Domicílio")

                resumo_linhas = []

                for item in resultado_domicilio.get("resumo", []):
                    resumo_linhas.append(
                        {
                            "Domicílio": item.get("domicilio", ""),
                            "Quantidade": item.get("total", 0)
                        }
                    )

                resumo_linhas.append(
                    {
                        "Domicílio": "TOTAL GERAL",
                        "Quantidade": total
                    }
                )

                st.dataframe(
                    pd.DataFrame(resumo_linhas),
                    use_container_width=True,
                    hide_index=True
                )

                try:
                    pdf_relatorio_domicilio = (
                        relatorios.gerar_pdf_relatorio_domicilio(
                            resultado_domicilio
                        )
                    )

                    coluna_imprimir, coluna_pdf = st.columns(2)

                    with coluna_imprimir:
                        pdf_base64_domicilio = base64.b64encode(
                            pdf_relatorio_domicilio
                        ).decode("utf-8")

                        components.html(
                            f"""
                            <button onclick="imprimirPDFDomicilio()" style="
                                width: 100%;
                                height: 38px;
                                background: #0056b3;
                                color: white;
                                border: 2px solid #0056b3;
                                border-radius: 12px;
                                font-weight: bold;
                                cursor: pointer;
                                font-family: sans-serif;
                            ">🖨️ Imprimir</button>

                            <script>
                            function imprimirPDFDomicilio() {{
                                const base64 = "{pdf_base64_domicilio}";
                                const binario = atob(base64);
                                const bytes = new Uint8Array(binario.length);

                                for (let i = 0; i < binario.length; i++) {{
                                    bytes[i] = binario.charCodeAt(i);
                                }}

                                const blob = new Blob(
                                    [bytes],
                                    {{type: "application/pdf"}}
                                );

                                const url = URL.createObjectURL(blob);
                                const janela = window.open(
                                    url,
                                    "_blank",
                                    "width=1000,height=800"
                                );

                                if (!janela) {{
                                    alert(
                                        "O navegador bloqueou o pop-up. "
                                        + "Permita pop-ups para este site."
                                    );
                                    return;
                                }}

                                setTimeout(function() {{
                                    try {{
                                        janela.focus();
                                        janela.print();
                                    }} catch (e) {{
                                    }}
                                }}, 1200);
                            }}
                            </script>
                            """,
                            height=45,
                            scrolling=False
                        )

                    with coluna_pdf:
                        st.download_button(
                            label="📄 Baixar PDF",
                            data=pdf_relatorio_domicilio,
                            file_name="relatorio_por_domicilio.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key="baixar_pdf_relatorio_domicilio"
                        )

                except Exception as erro_pdf:
                    st.error(
                        f"Não foi possível gerar o PDF: {erro_pdf}"
                    )

    # ========================================================
    # RELATÓRIO DE CRUZAMENTOS
    # ========================================================

    elif tipo_relatorio == "🔀 Cruzamentos":

        consulta_concorrentes = sheets.carregar_concorrentes(
            WEBHOOK_URL
        )

        if not consulta_concorrentes.get("sucesso"):
            st.error(
                consulta_concorrentes.get(
                    "mensagem",
                    "Não foi possível carregar as bases concorrentes."
                )
            )

        else:
            bases_concorrentes = consulta_concorrentes.get("bases", {})

            filtros_disponiveis = relatorios.obter_filtros_cruzamentos(
                base,
                bases_concorrentes
            )

            col_sup, col_sub, col_sit = st.columns(3)

            with col_sup:
                filtro_supervisor = st.selectbox(
                    "Supervisor",
                    ["Todos"] + filtros_disponiveis.get(
                        "supervisores",
                        []
                    ),
                    key="relatorio_cruzamentos_supervisor"
                )

            with col_sub:
                filtro_subsupervisor = st.selectbox(
                    "Subsupervisor",
                    ["Todos"] + filtros_disponiveis.get(
                        "subsupervisores",
                        []
                    ),
                    key="relatorio_cruzamentos_subsupervisor"
                )

            with col_sit:
                filtro_situacao = st.selectbox(
                    "Situação",
                    ["Todas"] + filtros_disponiveis.get(
                        "situacoes",
                        []
                    ),
                    key="relatorio_cruzamentos_situacao"
                )

            col_base, col_resultado = st.columns(2)

            with col_base:
                filtro_base_cruzada = st.selectbox(
                    "Base cruzada",
                    ["Todas"] + filtros_disponiveis.get(
                        "bases",
                        []
                    ),
                    key="relatorio_cruzamentos_base"
                )

            with col_resultado:
                filtro_resultado_cruzamento = st.selectbox(
                    "Resultado",
                    [
                        "Todos",
                        "Cruzou",
                        "Não cruzou"
                    ],
                    key="relatorio_cruzamentos_resultado"
                )

            gerar_cruzamentos = st.button(
                "🔎 Gerar relatório",
                type="primary",
                use_container_width=True,
                key="gerar_relatorio_cruzamentos"
            )

            if gerar_cruzamentos:
                st.session_state["relatorio_cruzamentos_gerado"] = (
                    relatorios.gerar_relatorio_cruzamentos(
                        dados_base=base,
                        bases_concorrentes=bases_concorrentes,
                        supervisor=(
                            ""
                            if filtro_supervisor == "Todos"
                            else filtro_supervisor
                        ),
                        subsupervisor=(
                            ""
                            if filtro_subsupervisor == "Todos"
                            else filtro_subsupervisor
                        ),
                        situacao=(
                            ""
                            if filtro_situacao == "Todas"
                            else filtro_situacao
                        ),
                        base_cruzada=(
                            ""
                            if filtro_base_cruzada == "Todas"
                            else filtro_base_cruzada
                        ),
                        resultado_cruzamento=(
                            ""
                            if filtro_resultado_cruzamento == "Todos"
                            else filtro_resultado_cruzamento
                        )
                    )
                )

            resultado_cruzamentos = st.session_state.get(
                "relatorio_cruzamentos_gerado"
            )

            if resultado_cruzamentos is not None:
                total = resultado_cruzamentos.get("total", 0)
                total_com = resultado_cruzamentos.get(
                    "total_com_cruzamento",
                    0
                )
                total_sem = resultado_cruzamentos.get(
                    "total_sem_cruzamento",
                    0
                )

                st.markdown(
                    f"""
                    <div style="
                        background:#ffffff;
                        border:1px solid #d9e1e8;
                        border-radius:10px;
                        padding:10px 14px;
                        margin:14px 0 12px 0;
                        font-size:0.95rem;
                    ">
                        <b>🔀 Relatório de Cruzamentos</b>
                        &nbsp;&nbsp; <b>{total}</b> registro(s)
                        &nbsp;&nbsp; <b>{total_com}</b> com cruzamento
                        &nbsp;&nbsp; <b>{total_sem}</b> sem cruzamento
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if total == 0:
                    st.info(
                        "Nenhum cadastro encontrado para os filtros selecionados."
                    )

                else:
                    for grupo in resultado_cruzamentos.get("grupos", []):
                        nome_supervisor = str(
                            grupo.get("supervisor", "SEM SUPERVISOR")
                        ).strip()

                        nome_subsupervisor = str(
                            grupo.get("subsupervisor", "SEM SUBSUPERVISOR")
                        ).strip()

                        registros_grupo = grupo.get("registros", [])

                        st.markdown(
                            f"""
                            <div style="
                                background:#f7f9fb;
                                border-left:4px solid #0056b3;
                                padding:8px 12px;
                                margin-top:12px;
                                margin-bottom:6px;
                                border-radius:6px;
                            ">
                                <b>Supervisor:</b> {nome_supervisor}
                                &nbsp;&nbsp;&nbsp;
                                <b>Subsupervisor:</b> {nome_subsupervisor}
                                &nbsp;&nbsp;&nbsp;
                                <b>Total:</b> {len(registros_grupo)}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                        linhas_tabela = []

                        for numero, registro in enumerate(
                            registros_grupo,
                            start=1
                        ):
                            cruzou = bool(
                                registro.get("cruzou_alguma")
                            )

                            marcador = (
                                "●"
                                if cruzou
                                else ""
                            )

                            numero_exibido = str(
                                numero
                            )

                            cruzamentos_texto = (
                                registro.get(
                                    "cruzamentos_texto",
                                    ""
                                )
                                or "—"
                            )

                            linhas_tabela.append(
                                {
                                    "●": marcador,
                                    "Nº": numero_exibido,
                                    "Nome": registro.get("nome", ""),
                                    "Comunidade": registro.get(
                                        "comunidade",
                                        ""
                                    ),
                                    "Telefone": registro.get(
                                        "telefone",
                                        ""
                                    ),
                                    "Cruzamentos": cruzamentos_texto
                                }
                            )

                        st.dataframe(
                            pd.DataFrame(linhas_tabela),
                            use_container_width=True,
                            hide_index=True,
                            height=min(
                                38 * len(linhas_tabela) + 38,
                                600
                            ),
                            column_config={
                                "●": st.column_config.TextColumn(
                                    "",
                                    width="small"
                                ),
                                "Nº": st.column_config.TextColumn(
                                    "Nº",
                                    width="small"
                                ),
                                "Nome": st.column_config.TextColumn(
                                    "Nome",
                                    width="large"
                                ),
                                "Comunidade": st.column_config.TextColumn(
                                    "Comunidade",
                                    width="medium"
                                ),
                                "Telefone": st.column_config.TextColumn(
                                    "Telefone",
                                    width="medium"
                                ),
                                "Cruzamentos": st.column_config.TextColumn(
                                    "Cruzamentos",
                                    width="large"
                                )
                            }
                        )

                    st.markdown("#### Resumo dos Cruzamentos")

                    resumo_linhas = []

                    for item in resultado_cruzamentos.get(
                        "resumo_bases",
                        []
                    ):
                        resumo_linhas.append(
                            {
                                "Base": item.get("base", ""),
                                "Cruzaram": item.get("cruzaram", 0),
                                "Não cruzaram": item.get(
                                    "nao_cruzaram",
                                    0
                                )
                            }
                        )

                    st.dataframe(
                        pd.DataFrame(resumo_linhas),
                        use_container_width=True,
                        hide_index=True
                    )

                    st.caption(
                        f"Com cruzamento em pelo menos uma base: {total_com} | "
                        f"Sem cruzamento em nenhuma base: {total_sem} | "
                        f"Total: {total}"
                    )

                    try:
                        pdf_cruzamentos = (
                            relatorios.gerar_pdf_relatorio_cruzamentos(
                                resultado_cruzamentos
                            )
                        )

                        coluna_imprimir, coluna_pdf = st.columns(2)

                        with coluna_imprimir:
                            pdf_base64_cruzamentos = base64.b64encode(
                                pdf_cruzamentos
                            ).decode("utf-8")

                            components.html(
                                f"""
                                <button onclick="imprimirPDFCruzamentos()" style="
                                    width: 100%;
                                    height: 38px;
                                    background: #0056b3;
                                    color: white;
                                    border: 2px solid #0056b3;
                                    border-radius: 12px;
                                    font-weight: bold;
                                    cursor: pointer;
                                    font-family: sans-serif;
                                ">🖨️ Imprimir</button>

                                <script>
                                function imprimirPDFCruzamentos() {{
                                    const base64 = "{pdf_base64_cruzamentos}";
                                    const binario = atob(base64);
                                    const bytes = new Uint8Array(binario.length);

                                    for (let i = 0; i < binario.length; i++) {{
                                        bytes[i] = binario.charCodeAt(i);
                                    }}

                                    const blob = new Blob(
                                        [bytes],
                                        {{type: "application/pdf"}}
                                    );

                                    const url = URL.createObjectURL(blob);
                                    const janela = window.open(
                                        url,
                                        "_blank",
                                        "width=1000,height=800"
                                    );

                                    if (!janela) {{
                                        alert(
                                            "O navegador bloqueou o pop-up. "
                                            + "Permita pop-ups para este site."
                                        );
                                        return;
                                    }}

                                    setTimeout(function() {{
                                        try {{
                                            janela.focus();
                                            janela.print();
                                        }} catch (e) {{
                                        }}
                                    }}, 1200);
                                }}
                                </script>
                                """,
                                height=45,
                                scrolling=False
                            )

                        with coluna_pdf:
                            st.download_button(
                                label="📄 Baixar PDF",
                                data=pdf_cruzamentos,
                                file_name="relatorio_de_cruzamentos.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                key="baixar_pdf_relatorio_cruzamentos"
                            )

                    except Exception as erro_pdf:
                        st.error(
                            f"Não foi possível gerar o PDF: {erro_pdf}"
                        )
