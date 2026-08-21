import re
import io
import gc
import unicodedata
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import fitz
from rapidocr import RapidOCR

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
# 5. OCR
#
# SÓ CARREGA SE REALMENTE PRECISAR
# ============================================================

def preparar_imagem(imagem):
    """Prepara a imagem para OCR preservando o fluxo original."""
    imagem = ImageOps.exif_transpose(imagem)
    imagem = imagem.convert("RGB")

    largura, altura = imagem.size

    if largura < 1200:
        proporcao = 1200 / largura
        imagem = imagem.resize(
            (1200, int(altura * proporcao)),
            Image.Resampling.LANCZOS
        )

    return imagem


_RAPIDOCR = None


def obter_rapidocr():
    """Carrega o RapidOCR uma única vez por processo."""
    global _RAPIDOCR
    if _RAPIDOCR is None:
        _RAPIDOCR = RapidOCR()
    return _RAPIDOCR


def _box_para_centro(box):
    if box is None:
        return 0.0, 0.0
    try:
        pontos = [(float(p[0]), float(p[1])) for p in box]
        xs = [p[0] for p in pontos]
        ys = [p[1] for p in pontos]
        return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    except Exception:
        return 0.0, 0.0


def executar_ocr_imagem(imagem):
    """
    OCR principal com RapidOCR.
    Preserva o formato esperado pelo extrator atual.
    """
    imagem = preparar_imagem(imagem)
    resultado = obter_rapidocr()(np.array(imagem))

    textos = getattr(resultado, "txts", None) or []
    scores = getattr(resultado, "scores", None) or []
    boxes = getattr(resultado, "boxes", None) or []

    itens = []

    for i, texto_bruto in enumerate(textos):
        texto = str(texto_bruto or "").strip()
        if not texto:
            continue

        confianca = 0.0
        if i < len(scores):
            try:
                confianca = float(scores[i])
            except Exception:
                pass

        box = boxes[i] if i < len(boxes) else None
        x, y = _box_para_centro(box)

        itens.append({
            "texto": texto,
            "confianca": confianca,
            "x": x,
            "y": y,
            "box": box,
        })

    itens.sort(key=lambda item: (round(item["y"] / 20), item["x"]))
    texto = "\n".join(item["texto"] for item in itens)

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
                250 / 72,
                250 / 72
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

    # Releitura direcionada do telefone manuscrito somente se necessário.
    telefone_ocr = encontrar_telefone_ocr(itens)
    if not telefone_ocr:
        telefone_ocr = recuperar_telefone_na_imagem(imagem, itens)

    if telefone_ocr:
        texto = (texto + "\nTELEFONE\n" + telefone_ocr).strip()
        itens.append({
            "texto": "TELEFONE",
            "confianca": 1.0,
            "x": 0.0,
            "y": 0.0,
            "box": None,
        })
        itens.append({
            "texto": telefone_ocr,
            "confianca": 1.0,
            "x": 0.0,
            "y": 20.0,
            "box": None,
        })

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
# 21B. EXTRAÇÃO OCR - TELEFONE / RELEITURA DIRECIONADA
# ============================================================

def _formatar_telefone_ocr(numero):
    numero = somente_numeros(numero)
    if len(numero) == 11:
        return f"({numero[:2]}) {numero[2:7]}-{numero[7:]}"
    if len(numero) == 10:
        return f"({numero[:2]}) {numero[2:6]}-{numero[6:]}"
    if len(numero) == 9:
        return f"{numero[:5]}-{numero[5:]}"
    if len(numero) == 8:
        return f"{numero[:4]}-{numero[4:]}"
    return numero


def encontrar_telefone_ocr(itens):
    """Procura telefone reconhecido perto de TELEFONE/FONE/CELULAR/CONTATO/WHATS."""
    rotulos = []
    for item in itens:
        r = normalizar_rotulo(item.get("texto", ""))
        if any(t in r for t in ("TELEFONE", "CELULAR", "FONE", "CONTATO", "WHATS")):
            rotulos.append(item)

    candidatos = []
    for item in itens:
        bruto = str(item.get("texto", "") or "")
        numero = somente_numeros(bruto)
        if len(numero) not in (8, 9, 10, 11):
            continue
        if len(numero) == 11 and cpf_valido(numero):
            continue

        pontos = float(item.get("confianca", 0) or 0) * 20
        if "-" in bruto:
            pontos += 15
        if "(" in bruto or ")" in bruto:
            pontos += 10

        if len(numero) == 11 and numero[2] == "9":
            pontos += 45
        elif len(numero) == 10 and numero[2] in "2345":
            pontos += 25
        elif len(numero) == 9 and numero[0] == "9":
            pontos += 40
        elif len(numero) == 8 and numero[0] in "2345":
            pontos += 15
        else:
            pontos -= 20

        for rotulo in rotulos:
            dx = abs(float(item.get("x", 0)) - float(rotulo.get("x", 0)))
            dy = float(item.get("y", 0)) - float(rotulo.get("y", 0))
            if -80 <= dy <= 300 and dx <= 900:
                pontos += 100 - min(70, abs(dy) * 0.15 + dx * 0.04)
                break

        candidatos.append((pontos, numero))

    if not candidatos:
        return ""

    candidatos.sort(reverse=True)
    pontos, numero = candidatos[0]
    return _formatar_telefone_ocr(numero) if pontos >= 55 else ""


def recuperar_telefone_na_imagem(imagem, itens):
    """
    Segunda passada somente quando o telefone não saiu na leitura principal.
    Recorta a faixa próxima ao rótulo e amplia/contrasta para tentar manuscrito.
    """
    rotulos = []
    for item in itens:
        r = normalizar_rotulo(item.get("texto", ""))
        if any(t in r for t in ("TELEFONE", "CELULAR", "FONE", "CONTATO", "WHATS")):
            rotulos.append(item)

    if not rotulos:
        return ""

    base = preparar_imagem(imagem)
    w, h = base.size

    for rotulo in rotulos:
        x = int(float(rotulo.get("x", 0)))
        y = int(float(rotulo.get("y", 0)))

        # Área larga: telefone manuscrito pode estar à direita ou logo abaixo.
        esquerda = max(0, x - 120)
        topo = max(0, y - 80)
        direita = min(w, x + 1200)
        baixo = min(h, y + 420)

        if direita <= esquerda or baixo <= topo:
            continue

        recorte = base.crop((esquerda, topo, direita, baixo))
        escala = 2.0
        recorte = recorte.resize(
            (max(1, int(recorte.width * escala)), max(1, int(recorte.height * escala))),
            Image.Resampling.LANCZOS
        )
        recorte = ImageOps.grayscale(recorte)
        recorte = ImageOps.autocontrast(recorte)
        recorte = ImageEnhance.Contrast(recorte).enhance(1.65)

        resultado = obter_rapidocr()(np.array(recorte))
        textos = getattr(resultado, "txts", None) or []
        scores = getattr(resultado, "scores", None) or []
        boxes = getattr(resultado, "boxes", None) or []

        novos = []
        for i, txt in enumerate(textos):
            txt = str(txt or "").strip()
            if not txt:
                continue
            score = float(scores[i]) if i < len(scores) else 0.0
            box = boxes[i] if i < len(boxes) else None
            cx, cy = _box_para_centro(box)
            novos.append({
                "texto": txt,
                "confianca": score,
                "x": cx,
                "y": cy,
                "box": box,
            })

        tel = encontrar_telefone_ocr(novos)
        if tel:
            return tel

        # Fallback restrito ao recorte: aceita padrão telefônico mesmo se
        # o rótulo ficou fora/ilegível na segunda passada.
        melhores = []
        for novo in novos:
            numero = somente_numeros(novo["texto"])
            if len(numero) in (8, 9, 10, 11):
                if len(numero) == 11 and cpf_valido(numero):
                    continue
                plausivel = (
                    (len(numero) == 11 and numero[2] == "9")
                    or (len(numero) == 10 and numero[2] in "2345")
                    or (len(numero) == 9 and numero[0] == "9")
                    or (len(numero) == 8 and numero[0] in "2345")
                )
                if plausivel:
                    melhores.append((novo["confianca"], numero))
        if melhores:
            melhores.sort(reverse=True)
            return _formatar_telefone_ocr(melhores[0][1])

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
