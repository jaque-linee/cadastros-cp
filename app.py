import streamlit as st
import requests
import re
import io
import gc
import unicodedata
import numpy as np
import pandas as pd
import base64
import streamlit.components.v1 as components
import relatorios
from PIL import Image, ImageOps
import fitz


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
# 5. OCR
#
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
#
# Não basta o PDF conter "algum texto".
# Ele precisa conter elementos compatíveis com documento.
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

    # --------------------------------------------
    # DATA
    # --------------------------------------------

    if re.search(
        r"\b\d{2}[\/.\-]\d{2}[\/.\-]\d{4}\b",
        texto
    ):
        pontos += 1

    # --------------------------------------------
    # CPF
    # --------------------------------------------

    if "CPF" in texto_normalizado:
        pontos += 1

    # --------------------------------------------
    # TÍTULO / INSCRIÇÃO
    # --------------------------------------------

    if (
        "INSCRICAO" in texto_normalizado
        or "TITULO" in texto_normalizado
    ):
        pontos += 1

    # --------------------------------------------
    # NOME
    # --------------------------------------------

    if "NOME" in texto_normalizado:
        pontos += 1

    # --------------------------------------------
    # FILIAÇÃO
    # --------------------------------------------

    if (
        "FILIACAO" in texto_normalizado
        or "MAE" in texto_normalizado
        or "NOME DA MAE" in texto_normalizado
    ):
        pontos += 1

    # --------------------------------------------
    # CNH
    # --------------------------------------------

    if (
        "CARTEIRA NACIONAL" in texto_normalizado
        or "HABILITACAO" in texto_normalizado
        or "REGISTRO" in texto_normalizado
    ):
        pontos += 1

    # --------------------------------------------
    # RG
    # --------------------------------------------

    if (
        "IDENTIDADE" in texto_normalizado
        or "REGISTRO GERAL" in texto_normalizado
    ):
        pontos += 1

    # Precisamos de pelo menos dois sinais reais
    # de que o texto representa os dados do documento.
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

    if nome.endswith(".pdf"):
        texto_nativo = extrair_texto_pdf(arquivo)

        # Primeiro tenta aproveitar a camada de texto, porque é muito mais leve.
        if pdf_tem_texto_util(texto_nativo):
            dados_nativos = extrair_dados_pdf_digital(texto_nativo)

            # Só encerra como PDF digital se a extração realmente trouxe
            # nome + nascimento + CPF/título confiáveis.
            if dados_digitais_suficientes(dados_nativos):
                return (
                    texto_nativo,
                    [],
                    "PDF — texto digital"
                )

        # A camada nativa não existe ou não foi suficiente/confiável.
        # Nesse caso, renderiza o PDF e usa OCR.
        texto, itens = executar_ocr_pdf(arquivo)

        return (
            texto,
            itens,
            "PDF — OCR"
        )

    # JPG / JPEG / PNG
    arquivo.seek(0)
    imagem = Image.open(arquivo)

    texto, itens = executar_ocr_imagem(imagem)

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
    """
    Extrai nome da mãe somente quando houver rótulo explícito.
    Não usa lista de nomes nem presume que o segundo nome de FILIAÇÃO é a mãe.
    """
    for i, linha in enumerate(linhas):
        rotulo = normalizar_rotulo(linha)

        if rotulo in ("MAE", "NOMEDAMAE", "NOMEMAE"):
            # Primeiro procura depois do rótulo.
            for deslocamento in (1, 2):
                pos = i + deslocamento
                if pos < len(linhas) and parece_nome(linhas[pos]):
                    return linhas[pos].upper()

            # Alguns PDFs posicionam visualmente o valor antes do rótulo.
            if i > 0 and parece_nome(linhas[i - 1]):
                return linhas[i - 1].upper()

    return ""


# ============================================================
# 16. EXTRAIR DADOS DO PDF DIGITAL
# ============================================================

def extrair_dados_pdf_digital(
    texto
):
    linhas = linhas_texto(
        texto
    )

    dados = {
        "nome": "",
        "cpf": "",
        "titulo": "",
        "data_nascimento": "",
        "nome_mae": "",
        "zona": "",
        "secao": ""
    }

    # ========================================================
    # NOME
    # ========================================================

    for i, linha in enumerate(
        linhas
    ):
        rotulo = normalizar_rotulo(
            linha
        )

        if rotulo in [
            "NOMEDOELEITOR",
            "NOME",
            "NOMECOMPLETO"
        ]:
            candidatos = []

            if i > 0:
                candidatos.append(
                    linhas[i - 1]
                )

            if i + 1 < len(linhas):
                candidatos.append(
                    linhas[i + 1]
                )

            for candidato in candidatos:
                if parece_nome(
                    candidato
                ):
                    dados["nome"] = (
                        candidato.upper()
                    )
                    break

        if dados["nome"]:
            break

    # ========================================================
    # NASCIMENTO
    # ========================================================

    for i, linha in enumerate(
        linhas
    ):
        rotulo = normalizar_rotulo(
            linha
        )

        if rotulo in [
            "DATADENASCIMENTO",
            "NASCIMENTO"
        ]:
            candidatos = []

            if i > 0:
                candidatos.append(
                    linhas[i - 1]
                )

            if i + 1 < len(linhas):
                candidatos.append(
                    linhas[i + 1]
                )

            for candidato in candidatos:
                if data_valida(
                    candidato
                ):
                    dados[
                        "data_nascimento"
                    ] = (
                        candidato
                        .replace(".", "/")
                        .replace("-", "/")
                    )
                    break

        if dados[
            "data_nascimento"
        ]:
            break

    # ========================================================
    # CPF
    # ========================================================

    for i, linha in enumerate(
        linhas
    ):
        if "CPF" in normalizar_texto(
            linha
        ):
            numero = somente_numeros(
                linha
            )

            if len(numero) == 11 and cpf_valido(numero):
                dados["cpf"] = formatar_cpf(
                    numero
                )
                break

            candidatos = []

            if i > 0:
                candidatos.append(
                    linhas[i - 1]
                )

            if i + 1 < len(linhas):
                candidatos.append(
                    linhas[i + 1]
                )

            for candidato in candidatos:
                numero = somente_numeros(
                    candidato
                )

                if len(numero) == 11 and cpf_valido(numero):
                    dados["cpf"] = formatar_cpf(
                        numero
                    )
                    break

        if dados["cpf"]:
            break

    # ========================================================
    # TÍTULO
    # ========================================================

    for i, linha in enumerate(
        linhas
    ):
        rotulo = normalizar_rotulo(
            linha
        )

        if rotulo in [
            "INSCRICAO",
            "TITULO"
        ]:
            candidatos = []

            if i > 0:
                candidatos.append(
                    linhas[i - 1]
                )

            if i + 1 < len(linhas):
                candidatos.append(
                    linhas[i + 1]
                )

            for candidato in candidatos:
                numero = somente_numeros(
                    candidato
                )

                if len(numero) == 12:
                    dados["titulo"] = numero
                    break

        if dados["titulo"]:
            break

    # Sem fallback global para título:
    # um número de 12 dígitos só é aceito quando estiver associado
    # ao rótulo INSCRIÇÃO/TÍTULO. Isso evita inventar título.

    # ========================================================
    # NOME DA MÃE
    # ========================================================

    dados["nome_mae"] = (
        encontrar_mae_texto_digital(
            linhas
        )
    )

    # ========================================================
    # ZONA
    # ========================================================

    for i, linha in enumerate(
        linhas
    ):
        if normalizar_rotulo(
            linha
        ) == "ZONA":
            candidatos = []

            if i > 0:
                candidatos.append(
                    linhas[i - 1]
                )

            if i + 1 < len(linhas):
                candidatos.append(
                    linhas[i + 1]
                )

            for candidato in candidatos:
                numero = somente_numeros(
                    candidato
                )

                if 1 <= len(numero) <= 3:
                    dados["zona"] = (
                        numero.zfill(3)
                    )
                    break

        if dados["zona"]:
            break

    # ========================================================
    # SEÇÃO
    # ========================================================

    for i, linha in enumerate(
        linhas
    ):
        if normalizar_rotulo(
            linha
        ) == "SECAO":
            candidatos = []

            if i > 0:
                candidatos.append(
                    linhas[i - 1]
                )

            if i + 1 < len(linhas):
                candidatos.append(
                    linhas[i + 1]
                )

            for candidato in candidatos:
                numero = somente_numeros(
                    candidato
                )

                if 1 <= len(numero) <= 4:
                    dados["secao"] = (
                        numero.zfill(4)
                    )
                    break

        if dados["secao"]:
            break

    return dados


# ============================================================
# 17. EXTRAÇÃO OCR - TÍTULO
# ============================================================

def encontrar_titulo_ocr(itens):
    """
    Extrai título somente quando um número de 12 dígitos está espacialmente
    associado a um rótulo INSCRIÇÃO/TÍTULO. Não usa qualquer número solto.
    """
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

        # O próprio bloco pode conter rótulo + número.
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

            # Aceita valor na mesma linha ou logo abaixo, sem varrer o documento.
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
    """
    Procura data de nascimento perto do rótulo correspondente.
    Não escolhe simplesmente a primeira data do documento.
    """
    rotulos = []

    for item in itens:
        rotulo = normalizar_rotulo(item["texto"])
        if (
            rotulo in ("DATADENASCIMENTO", "NASCIMENTO", "DTNASCIMENTO")
            or "NASCIMENTO" in rotulo
        ):
            rotulos.append(item)

    for rotulo in rotulos:
        candidatos = []

        for item in itens:
            texto = str(item["texto"])

            for match in re.finditer(
                r"\b(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})\b",
                texto
            ):
                valor = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                if not data_valida(valor):
                    continue

                dx = abs(item["x"] - rotulo["x"])
                dy = item["y"] - rotulo["y"]

                if -60 <= dy <= 220 and dx <= 650:
                    candidatos.append(
                        (abs(dy) + dx * 0.2, -item["confianca"], valor)
                    )

        if candidatos:
            candidatos.sort()
            return candidatos[0][2]

    return ""


# ============================================================
# 19. EXTRAÇÃO OCR - CPF
# ============================================================

def encontrar_cpf_ocr(
    itens
):
    # --------------------------------------------
    # PRIMEIRO PROCURA PERTO DE "CPF"
    # --------------------------------------------

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

    # --------------------------------------------
    # FALLBACK:
    # qualquer número de 11 dígitos
    # --------------------------------------------

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

def encontrar_nome_ocr(
    itens
):
    # --------------------------------------------
    # PRIMEIRO PROCURA RÓTULO
    # --------------------------------------------

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

    # --------------------------------------------
    # FALLBACK
    # --------------------------------------------

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
    """
    Extrai o nome da mãe somente com evidência estrutural:
    rótulo MÃE/NOME DA MÃE ou rótulo equivalente.
    FILIAÇÃO isolada não é suficiente para decidir qual nome é o da mãe.
    """
    rotulos_mae = []

    for item in itens:
        rotulo = normalizar_rotulo(item["texto"])
        if (
            rotulo in ("MAE", "NOMEDAMAE", "NOMEMAE")
            or "NOMEDAMAE" in rotulo
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

            if -50 <= dy <= 230 and dx <= 750:
                candidatos.append(
                    (
                        abs(dy) + dx * 0.2,
                        -item["confianca"],
                        candidato.upper()
                    )
                )

        if candidatos:
            candidatos.sort()
            return candidatos[0][2]

    # Não deduz mãe pelo sexo, primeiro nome ou posição arbitrária.
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

            # Não usar datas
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
        "secao": secao
    }


# ============================================================
# 23B. QUALIDADE DOS DADOS EXTRAÍDOS DO PDF DIGITAL
# ============================================================

def dados_digitais_suficientes(dados):
    """
    Só aceita a camada de texto nativa do PDF quando ela produziu
    dados pessoais minimamente confiáveis. Caso contrário, o PDF
    será renderizado e lido por OCR.
    """
    nome = str(dados.get("nome", "") or "").strip()
    nascimento = str(dados.get("data_nascimento", "") or "").strip()
    cpf = str(dados.get("cpf", "") or "").strip()
    titulo = str(dados.get("titulo", "") or "").strip()

    identificador_valido = (
        (cpf and cpf_valido(cpf))
        or len(somente_numeros(titulo)) == 12
    )

    return bool(
        nome
        and parece_nome(nome)
        and nascimento
        and data_valida(nascimento)
        and identificador_valido
    )


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
#
# Nome
# + nascimento
# + nome da mãe
# + CPF OU título
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

    return (
        sorted(
            supervisores
        ),
        sorted(
            subs
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

lista_sup, lista_sub = obter_supervisores(
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

    st.markdown(
        "---"
    )

    menu = st.radio(
        "Escolha a Operação:",
        [
            "📸 Envio de Documentos",
            "✍️ Formulário Manual",
            "📊 Relatórios"
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
        f"Subsupervisor: {sub}"
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
                                existente_sup
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

            df_resultados = pd.DataFrame(
                resultados
            )

            st.dataframe(
                df_resultados,
                use_container_width=True,
                hide_index=True
            )

            st.caption(
                "ℹ️ Para ser considerado completo: "
                "Nome + Nascimento + Nome da mãe + "
                "CPF ou Título. "
                "Nenhum cadastro do lote foi gravado "
                "automaticamente."
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
                                sub
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


# ============================================================
# 28. RELATÓRIOS
# ============================================================

elif menu == "📊 Relatórios":
    st.subheader("📊 Relatórios")
    st.caption("Consulte a base cadastrada de forma rápida e organizada.")

    tipo_relatorio = st.selectbox(
        "Tipo de relatório",
        ["👤 Por Nome", "📍 Por Zona", "🏠 Por Domicílio", "🔀 Cruzamentos"],
        key="tipo_relatorio"
    )

    # ============================================================
    # RELATÓRIO POR NOME
    # ============================================================
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

        gerar_relatorio = st.button("🔎 Gerar relatório", type="primary", use_container_width=True, key="gerar_relatorio_nome")

        if gerar_relatorio:
            st.session_state["relatorio_nome_gerado"] = relatorios.gerar_relatorio_nome(
                dados_base=base,
                supervisor="" if filtro_supervisor == "Todos" else filtro_supervisor,
                subsupervisor="" if filtro_subsupervisor == "Todos" else filtro_subsupervisor,
                situacao="" if filtro_situacao == "Todas" else filtro_situacao
            )

        resultado_relatorio = st.session_state.get("relatorio_nome_gerado")

        if resultado_relatorio is not None:
            total_relatorio = resultado_relatorio.get("total", 0)

            st.markdown(
                f"""
                <div style="background:#ffffff;border:1px solid #d9e1e8;border-radius:10px;padding:10px 14px;margin:14px 0 12px 0;font-size:0.95rem;">
                    <b>👤 Relatório por Nome</b> &nbsp;&nbsp; <b>{total_relatorio}</b> registro(s)
                </div>
                """,
                unsafe_allow_html=True
            )

            if total_relatorio == 0:
                st.info("Nenhum cadastro encontrado para os filtros selecionados.")
            else:
                for grupo in resultado_relatorio.get("grupos", []):
                    nome_supervisor = str(grupo.get("supervisor", "SEM SUPERVISOR")).strip()
                    nome_subsupervisor = str(grupo.get("subsupervisor", "SEM SUBSUPERVISOR")).strip()
                    registros_grupo = grupo.get("registros", [])

                    st.markdown(
                        f"""
                        <div style="background:#f7f9fb;border-left:4px solid #0056b3;padding:8px 12px;margin-top:12px;margin-bottom:6px;border-radius:6px;">
                            <b>Supervisor:</b> {nome_supervisor} &nbsp;&nbsp;&nbsp; <b>Subsupervisor:</b> {nome_subsupervisor} &nbsp;&nbsp;&nbsp; <b>Total:</b> {len(registros_grupo)}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    linhas_tabela = []
                    for numero, registro in enumerate(registros_grupo, start=1):
                        linhas_tabela.append({
                            "Nº": numero,
                            "Nome": str(registro.get("nome", "")).strip(),
                            "Comunidade": str(registro.get("comunidade", "")).strip(),
                            "Telefone": str(registro.get("telefone", "")).strip()
                        })

                    tabela_grupo = pd.DataFrame(linhas_tabela)
                    st.dataframe(tabela_grupo, use_container_width=True, hide_index=True, height=min(38 * len(tabela_grupo) + 38, 500))

            if total_relatorio > 0:
                try:
                    pdf_relatorio = relatorios.gerar_pdf_relatorio_nome(resultado_relatorio)

                    coluna_imprimir, coluna_pdf = st.columns(2)

                    with coluna_imprimir:
                        pdf_base64 = base64.b64encode(pdf_relatorio).decode("utf-8")
                        components.html(
                            f"""
                            <button onclick="imprimirPDFNome()" style="width:100%;height:38px;background:#0056b3;color:white;border:2px solid #0056b3;border-radius:12px;font-weight:bold;cursor:pointer;font-family:sans-serif;">🖨️ Imprimir</button>
                            <script>
                            function imprimirPDFNome() {{
                                const base64 = "{pdf_base64}";
                                const binario = atob(base64);
                                const bytes = new Uint8Array(binario.length);
                                for (let i = 0; i < binario.length; i++) {{
                                    bytes[i] = binario.charCodeAt(i);
                                }}
                                const blob = new Blob([bytes], {{type: "application/pdf"}});
                                const url = URL.createObjectURL(blob);
                                const janela = window.open(url, "_blank", "width=1000,height=800");
                                if (!janela) {{
                                    alert("O navegador bloqueou o pop-up. Permita pop-ups para este site.");
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
                    st.error(f"Não foi possível gerar o PDF: {erro_pdf}")

    # ============================================================
    # RELATÓRIO POR ZONA
    # ============================================================
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

        secoes_disponiveis = relatorios.obter_secoes_por_zona(base, "" if filtro_zona == "Todas" else filtro_zona)

        with col_secao:
            filtro_secao = st.selectbox(
                "Seção",
                ["Todas"] + secoes_disponiveis,
                key="relatorio_zona_secao"
            )

        gerar_relatorio_zona = st.button("🔎 Gerar relatório", type="primary", use_container_width=True, key="gerar_relatorio_zona")

        if gerar_relatorio_zona:
            st.session_state["relatorio_zona_gerado"] = relatorios.gerar_relatorio_zona(
                dados_base=base,
                supervisor="" if filtro_supervisor == "Todos" else filtro_supervisor,
                subsupervisor="" if filtro_subsupervisor == "Todos" else filtro_subsupervisor,
                zona="" if filtro_zona == "Todas" else filtro_zona,
                secao="" if filtro_secao == "Todas" else filtro_secao,
                situacao="" if filtro_situacao == "Todas" else filtro_situacao
            )

        resultado_zona = st.session_state.get("relatorio_zona_gerado")

        if resultado_zona is not None:
            total = resultado_zona.get("total", 0)
            total_zonas = resultado_zona.get("total_zonas", 0)
            total_secoes = resultado_zona.get("total_secoes", 0)

            st.markdown(
                f"""
                <div style="background:#ffffff;border:1px solid #d9e1e8;border-radius:10px;padding:10px 14px;margin:14px 0 12px 0;font-size:0.95rem;">
                    <b>📍 Relatório por Zona</b> &nbsp;&nbsp; <b>{total}</b> registro(s) &nbsp;&nbsp; <b>{total_zonas}</b> zona(s) &nbsp;&nbsp; <b>{total_secoes}</b> seção(ões)
                </div>
                """,
                unsafe_allow_html=True
            )

            if total == 0:
                st.info("Nenhum cadastro encontrado para os filtros selecionados.")
            else:
                linhas = []
                for numero, registro in enumerate(resultado_zona.get("registros", []), start=1):
                    linhas.append({
                        "Nº": numero,
                        "Zona": registro.get("zona", ""),
                        "Seção": registro.get("secao", ""),
                        "Nome": registro.get("nome", ""),
                        "Comunidade": registro.get("comunidade", ""),
                        "Telefone": registro.get("telefone", "")
                    })

                tabela_zona = pd.DataFrame(linhas)
                st.dataframe(tabela_zona, use_container_width=True, hide_index=True, height=min(38 * len(tabela_zona) + 38, 600))

                st.markdown("#### Resumo por Zona e Seção")

                resumo_linhas = []
                for grupo in resultado_zona.get("resumo", []):
                    zona_atual = grupo.get("zona", "")
                    for item in grupo.get("secoes", []):
                        resumo_linhas.append({
                            "Zona": zona_atual,
                            "Seção": item.get("secao", ""),
                            "Quantidade": item.get("total", 0)
                        })
                    resumo_linhas.append({
                        "Zona": f"TOTAL ZONA {zona_atual}",
                        "Seção": "",
                        "Quantidade": grupo.get("total", 0)
                    })

                resumo_linhas.append({
                    "Zona": "TOTAL GERAL",
                    "Seção": "",
                    "Quantidade": total
                })

                st.dataframe(pd.DataFrame(resumo_linhas), use_container_width=True, hide_index=True)

                try:
                    pdf_relatorio_zona = relatorios.gerar_pdf_relatorio_zona(resultado_zona)

                    coluna_imprimir, coluna_pdf = st.columns(2)

                    with coluna_imprimir:
                        pdf_base64_zona = base64.b64encode(pdf_relatorio_zona).decode("utf-8")
                        components.html(
                            f"""
                            <button onclick="imprimirPDFZona()" style="width:100%;height:38px;background:#0056b3;color:white;border:2px solid #0056b3;border-radius:12px;font-weight:bold;cursor:pointer;font-family:sans-serif;">🖨️ Imprimir</button>
                            <script>
                            function imprimirPDFZona() {{
                                const base64 = "{pdf_base64_zona}";
                                const binario = atob(base64);
                                const bytes = new Uint8Array(binario.length);
                                for (let i = 0; i < binario.length; i++) {{
                                    bytes[i] = binario.charCodeAt(i);
                                }}
                                const blob = new Blob([bytes], {{type: "application/pdf"}});
                                const url = URL.createObjectURL(blob);
                                const janela = window.open(url, "_blank", "width=1000,height=800");
                                if (!janela) {{
                                    alert("O navegador bloqueou o pop-up. Permita pop-ups para este site.");
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
                    st.error(f"Não foi possível gerar o PDF: {erro_pdf}")

    # ============================================================
    # RELATÓRIO POR DOMICÍLIO
    # ============================================================
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

        gerar_relatorio_domicilio = st.button("🔎 Gerar relatório", type="primary", use_container_width=True, key="gerar_relatorio_domicilio")

        if gerar_relatorio_domicilio:
            st.session_state["relatorio_domicilio_gerado"] = relatorios.gerar_relatorio_domicilio(
                dados_base=base,
                supervisor="" if filtro_supervisor == "Todos" else filtro_supervisor,
                subsupervisor="" if filtro_subsupervisor == "Todos" else filtro_subsupervisor,
                domicilio="" if filtro_domicilio == "Todos" else filtro_domicilio,
                situacao="" if filtro_situacao == "Todas" else filtro_situacao
            )

        resultado_domicilio = st.session_state.get("relatorio_domicilio_gerado")

        if resultado_domicilio is not None:
            total = resultado_domicilio.get("total", 0)
            total_domicilios = resultado_domicilio.get("total_domicilios", 0)

            st.markdown(
                f"""
                <div style="background:#ffffff;border:1px solid #d9e1e8;border-radius:10px;padding:10px 14px;margin:14px 0 12px 0;font-size:0.95rem;">
                    <b>🏠 Relatório por Domicílio</b> &nbsp;&nbsp; <b>{total}</b> registro(s) &nbsp;&nbsp; <b>{total_domicilios}</b> domicílio(s)
                </div>
                """,
                unsafe_allow_html=True
            )

            if total == 0:
                st.info("Nenhum cadastro encontrado para os filtros selecionados.")
            else:
                linhas = []
                for numero, registro in enumerate(resultado_domicilio.get("registros", []), start=1):
                    linhas.append({
                        "Nº": numero,
                        "Domicílio": registro.get("domicilio", ""),
                        "Nome": registro.get("nome", ""),
                        "Comunidade": registro.get("comunidade", ""),
                        "Telefone": registro.get("telefone", "")
                    })

                tabela_domicilio = pd.DataFrame(linhas)
                st.dataframe(tabela_domicilio, use_container_width=True, hide_index=True, height=min(38 * len(tabela_domicilio) + 38, 600))

                st.markdown("#### Resumo por Domicílio")

                resumo_linhas = []
                for item in resultado_domicilio.get("resumo", []):
                    resumo_linhas.append({
                        "Domicílio": item.get("domicilio", ""),
                        "Quantidade": item.get("total", 0)
                    })

                resumo_linhas.append({
                    "Domicílio": "TOTAL GERAL",
                    "Quantidade": total
                })

                st.dataframe(pd.DataFrame(resumo_linhas), use_container_width=True, hide_index=True)

                try:
                    pdf_relatorio_domicilio = relatorios.gerar_pdf_relatorio_domicilio(resultado_domicilio)

                    coluna_imprimir, coluna_pdf = st.columns(2)

                    with coluna_imprimir:
                        pdf_base64_domicilio = base64.b64encode(pdf_relatorio_domicilio).decode("utf-8")
                        components.html(
                            f"""
                            <button onclick="imprimirPDFDomicilio()" style="width:100%;height:38px;background:#0056b3;color:white;border:2px solid #0056b3;border-radius:12px;font-weight:bold;cursor:pointer;font-family:sans-serif;">🖨️ Imprimir</button>
                            <script>
                            function imprimirPDFDomicilio() {{
                                const base64 = "{pdf_base64_domicilio}";
                                const binario = atob(base64);
                                const bytes = new Uint8Array(binario.length);
                                for (let i = 0; i < binario.length; i++) {{
                                    bytes[i] = binario.charCodeAt(i);
                                }}
                                const blob = new Blob([bytes], {{type: "application/pdf"}});
                                const url = URL.createObjectURL(blob);
                                const janela = window.open(url, "_blank", "width=1000,height=800");
                                if (!janela) {{
                                    alert("O navegador bloqueou o pop-up. Permita pop-ups para este site.");
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
                    st.error(f"Não foi possível gerar o PDF: {erro_pdf}")

    # ============================================================
    # RELATÓRIO DE CRUZAMENTOS
    # ============================================================
    elif tipo_relatorio == "🔀 Cruzamentos":
        consulta_concorrentes = sheets.carregar_concorrentes(WEBHOOK_URL)

        if not consulta_concorrentes.get("sucesso"):
            st.error(consulta_concorrentes.get("mensagem", "Não foi possível carregar as bases concorrentes."))
        else:
            bases_concorrentes = consulta_concorrentes.get("dados", {})

            filtros_disponiveis = relatorios.obter_filtros_cruzamentos(base, bases_concorrentes)

            col_sup, col_sub, col_sit = st.columns(3)

            with col_sup:
                filtro_supervisor = st.selectbox(
                    "Supervisor",
                    ["Todos"] + filtros_disponiveis.get("supervisores", []),
                    key="relatorio_cruzamentos_supervisor"
                )

            with col_sub:
                filtro_subsupervisor = st.selectbox(
                    "Subsupervisor",
                    ["Todos"] + filtros_disponiveis.get("subsupervisores", []),
                    key="relatorio_cruzamentos_subsupervisor"
                )

            with col_sit:
                filtro_situacao = st.selectbox(
                    "Situação",
                    ["Todas"] + filtros_disponiveis.get("situacoes", []),
                    key="relatorio_cruzamentos_situacao"
                )

            col_base, col_resultado = st.columns(2)

            with col_base:
                filtro_base_cruzada = st.selectbox(
                    "Base cruzada",
                    ["Todas"] + filtros_disponiveis.get("bases", []),
                    key="relatorio_cruzamentos_base"
                )

            with col_resultado:
                filtro_resultado_cruzamento = st.selectbox(
                    "Resultado",
                    ["Todos", "Cruzou", "Não cruzou"],
                    key="relatorio_cruzamentos_resultado"
                )

            gerar_cruzamentos = st.button("🔎 Gerar relatório", type="primary", use_container_width=True, key="gerar_relatorio_cruzamentos")

            if gerar_cruzamentos:
                st.session_state["relatorio_cruzamentos_gerado"] = relatorios.gerar_relatorio_cruzamentos(
                    dados_base=base,
                    bases_concorrentes=bases_concorrentes,
                    supervisor="" if filtro_supervisor == "Todos" else filtro_supervisor,
                    subsupervisor="" if filtro_subsupervisor == "Todos" else filtro_subsupervisor,
                    situacao="" if filtro_situacao == "Todas" else filtro_situacao,
                    base_cruzada="" if filtro_base_cruzada == "Todas" else filtro_base_cruzada,
                    resultado_cruzamento="" if filtro_resultado_cruzamento == "Todos" else filtro_resultado_cruzamento
                )

            resultado_cruzamentos = st.session_state.get("relatorio_cruzamentos_gerado")

            if resultado_cruzamentos is not None:
                total = resultado_cruzamentos.get("total", 0)
                total_com = resultado_cruzamentos.get("total_com_cruzamento", 0)
                total_sem = resultado_cruzamentos.get("total_sem_cruzamento", 0)

                st.markdown(
                    f"""
                    <div style="background:#ffffff;border:1px solid #d9e1e8;border-radius:10px;padding:10px 14px;margin:14px 0 12px 0;font-size:0.95rem;">
                        <b>🔀 Relatório de Cruzamentos</b> &nbsp;&nbsp; <b>{total}</b> registro(s) &nbsp;&nbsp; <b>{total_com}</b> com cruzamento &nbsp;&nbsp; <b>{total_sem}</b> sem cruzamento
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if total == 0:
                    st.info("Nenhum cadastro encontrado para os filtros selecionados.")
                else:
                    for grupo in resultado_cruzamentos.get("grupos", []):
                        nome_supervisor = str(grupo.get("supervisor", "SEM SUPERVISOR")).strip()
                        nome_subsupervisor = str(grupo.get("subsupervisor", "SEM SUBSUPERVISOR")).strip()
                        registros_grupo = grupo.get("registros", [])

                        st.markdown(
                            f"""
                            <div style="background:#f7f9fb;border-left:4px solid #0056b3;padding:8px 12px;margin-top:12px;margin-bottom:6px;border-radius:6px;">
                                <b>Supervisor:</b> {nome_supervisor} &nbsp;&nbsp;&nbsp; <b>Subsupervisor:</b> {nome_subsupervisor} &nbsp;&nbsp;&nbsp; <b>Total:</b> {len(registros_grupo)}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                        linhas_tabela = []
                        for numero, registro in enumerate(registros_grupo, start=1):
                            cruzou = bool(registro.get("cruzou_alguma"))
                            marcador = "●" if cruzou else ""
                            cruzamentos_texto = registro.get("cruzamentos_texto", "") or "—"

                            linhas_tabela.append({
                                "●": marcador,
                                "Nº": str(numero),
                                "Nome": registro.get("nome", ""),
                                "Comunidade": registro.get("comunidade", ""),
                                "Telefone": registro.get("telefone", ""),
                                "Cruzamentos": cruzamentos_texto
                            })

                        st.dataframe(
                            pd.DataFrame(linhas_tabela),
                            use_container_width=True,
                            hide_index=True,
                            height=min(38 * len(linhas_tabela) + 38, 600),
                            column_config={
                                "●": st.column_config.TextColumn("", width="small"),
                                "Nº": st.column_config.TextColumn("Nº", width="small"),
                                "Nome": st.column_config.TextColumn("Nome", width="large"),
                                "Comunidade": st.column_config.TextColumn("Comunidade", width="medium"),
                                "Telefone": st.column_config.TextColumn("Telefone", width="medium"),
                                "Cruzamentos": st.column_config.TextColumn("Cruzamentos", width="large")
                            }
                        )

                    st.markdown("#### Resumo dos Cruzamentos")

                    resumo_linhas = []
                    for item in resultado_cruzamentos.get("resumo_bases", []):
                        resumo_linhas.append({
                            "Base": item.get("base", ""),
                            "Cruzaram": item.get("cruzaram", 0),
                            "Não cruzaram": item.get("nao_cruzaram", 0)
                        })

                    st.dataframe(pd.DataFrame(resumo_linhas), use_container_width=True, hide_index=True)

                    st.caption(f"Com cruzamento em pelo menos uma base: {total_com} | Sem cruzamento em nenhuma base: {total_sem} | Total: {total}")

                    try:
                        pdf_cruzamentos = relatorios.gerar_pdf_relatorio_cruzamentos(resultado_cruzamentos)

                        coluna_imprimir, coluna_pdf = st.columns(2)

                        with coluna_imprimir:
                            pdf_base64_cruzamentos = base64.b64encode(pdf_cruzamentos).decode("utf-8")
                            components.html(
                                f"""
                                <button onclick="imprimirPDFCruzamentos()" style="width:100%;height:38px;background:#0056b3;color:white;border:2px solid #0056b3;border-radius:12px;font-weight:bold;cursor:pointer;font-family:sans-serif;">🖨️ Imprimir</button>
                                <script>
                                function imprimirPDFCruzamentos() {{
                                    const base64 = "{pdf_base64_cruzamentos}";
                                    const binario = atob(base64);
                                    const bytes = new Uint8Array(binario.length);
                                    for (let i = 0; i < binario.length; i++) {{
                                        bytes[i] = binario.charCodeAt(i);
                                    }}
                                    const blob = new Blob([bytes], {{type: "application/pdf"}});
                                    const url = URL.createObjectURL(blob);
                                    const janela = window.open(url, "_blank", "width=1000,height=800");
                                    if (!janela) {{
                                        alert("O navegador bloqueou o pop-up. Permita pop-ups para este site.");
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
                        st.error(f"Não foi possível gerar o PDF: {erro_pdf}")
