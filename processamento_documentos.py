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

        largura, altura = imagem.size

        itens.append({
            "texto": texto,
            "confianca": confianca,
            "pagina": 1,
            "largura_pagina": largura,
            "altura_pagina": altura,
            "x": x,
            "y": y,
            "x_relativo": (x / largura) if largura else None,
            "y_relativo": (y / altura) if altura else None,
            "box": box,
        })

    # Mantém a ordem original do RapidOCR, como no teste do VSCode.
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

        for item in itens:
            item["pagina"] = numero_pagina + 1

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
# MOTOR RAPIDOCR DO VSCODE - INCORPORADO AO STREAMLIT
# ============================================================

import re
import unicodedata
from datetime import datetime


# ============================================================
# UTILIDADES
# ============================================================

def limpar_texto(valor):
    if valor is None:
        return ""
    return re.sub(r"\s+", " ", str(valor)).strip()


def sem_acentos(valor):
    valor = limpar_texto(valor)

    return "".join(
        c for c in unicodedata.normalize("NFD", valor)
        if unicodedata.category(c) != "Mn"
    ).upper()


def somente_numeros(valor):
    return re.sub(r"\D", "", limpar_texto(valor))


def texto(bloco):
    """
    IMPORTANTE:
    Agora o extrator recebe os dicionários criados
    pelo teste_ocr.py.
    """
    if isinstance(bloco, dict):
        return limpar_texto(bloco.get("texto", ""))

    return limpar_texto(bloco)


def confianca(bloco):
    if not isinstance(bloco, dict):
        return 0.0

    try:
        return float(bloco.get("confianca") or 0)
    except Exception:
        return 0.0


# ============================================================
# NORMALIZAÇÃO PARA COMPARAR RÓTULOS
# ============================================================

def compacto(valor):
    return re.sub(
        r"[^A-Z0-9]",
        "",
        sem_acentos(valor)
    )


def contem_algum(valor, termos):
    normal = sem_acentos(valor)
    comp = compacto(valor)

    for termo in termos:
        termo_normal = sem_acentos(termo)
        termo_comp = compacto(termo)

        if termo_normal in normal:
            return True

        if len(termo_comp) >= 5 and termo_comp in comp:
            return True

    return False


# ============================================================
# CPF
# ============================================================

def cpf_valido(numero):
    numero = somente_numeros(numero)

    if len(numero) != 11:
        return False

    if numero == numero[0] * 11:
        return False

    try:
        soma = sum(
            int(numero[i]) * (10 - i)
            for i in range(9)
        )

        resto = soma % 11
        d1 = 0 if resto < 2 else 11 - resto

        soma = sum(
            int(numero[i]) * (11 - i)
            for i in range(10)
        )

        resto = soma % 11
        d2 = 0 if resto < 2 else 11 - resto

        return numero[-2:] == f"{d1}{d2}"

    except Exception:
        return False


def formatar_cpf(numero):
    numero = somente_numeros(numero)

    return (
        f"{numero[:3]}."
        f"{numero[3:6]}."
        f"{numero[6:9]}-"
        f"{numero[9:]}"
    )


def extrair_cpf(blocos):
    # Primeiro: CPF matematicamente válido.
    for bloco in blocos:
        numero = somente_numeros(texto(bloco))

        if len(numero) == 11 and cpf_valido(numero):
            return formatar_cpf(numero)

    # Segundo: número de 11 dígitos explicitamente
    # associado a CPF.
    for i, bloco in enumerate(blocos):
        if not contem_algum(texto(bloco), ["CPF"]):
            continue

        for j in range(i, min(i + 4, len(blocos))):
            numero = somente_numeros(texto(blocos[j]))

            if len(numero) == 11:
                return formatar_cpf(numero)

    return ""


# ============================================================
# DATA DE NASCIMENTO
# ============================================================

PADRAO_DATA = re.compile(
    r"\b"
    r"(0?[1-9]|[12]\d|3[01])"
    r"[\/\-.]"
    r"(0?[1-9]|1[0-2])"
    r"[\/\-.]"
    r"((?:19|20)\d{2})"
    r"\b"
)


def extrair_datas(valor):
    encontrados = []

    for match in PADRAO_DATA.finditer(texto(valor)):
        dia = int(match.group(1))
        mes = int(match.group(2))
        ano = int(match.group(3))

        try:
            data = datetime(ano, mes, dia)
            encontrados.append(data)
        except ValueError:
            pass

    return encontrados


def extrair_nascimento(blocos):
    candidatos = []

    ano_atual = datetime.now().year

    for indice, bloco in enumerate(blocos):
        for data in extrair_datas(bloco):

            pontos = 0

            idade = ano_atual - data.year

            # Cadastro de adulto: forte indício.
            if 16 <= idade <= 110:
                pontos += 40
            elif 0 <= idade <= 110:
                pontos += 10

            # Confiança do OCR.
            pontos += confianca(bloco) * 10

            # Procura contexto próximo na ORDEM do OCR.
            inicio = max(0, indice - 4)
            fim = min(len(blocos), indice + 5)

            contexto = " ".join(
                sem_acentos(texto(b))
                for b in blocos[inicio:fim]
            )

            if any(
                marcador in contexto
                for marcador in [
                    "NASCIMENTO",
                    "NASC",
                    "NASCIME",
                    "DATA DE NASC"
                ]
            ):
                pontos += 60

            if any(
                marcador in contexto
                for marcador in [
                    "EMISSAO",
                    "VALIDADE",
                    "EXPEDICAO"
                ]
            ):
                pontos -= 30

            candidatos.append(
                (pontos, data)
            )

    if not candidatos:
        return ""

    candidatos.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return candidatos[0][1].strftime("%d/%m/%Y")


# ============================================================
# TÍTULO ELEITORAL
# ============================================================

def extrair_titulo(blocos):
    candidatos = []

    for indice, bloco in enumerate(blocos):
        valor = texto(bloco)
        numero = somente_numeros(valor)

        if len(numero) != 12:
            continue

        pontos = 20

        # Título frequentemente aparece agrupado:
        # 0417 1503 1791
        if len(valor.split()) >= 2:
            pontos += 15

        inicio = max(0, indice - 12)
        fim = min(len(blocos), indice + 5)

        contexto = " ".join(
            sem_acentos(texto(b))
            for b in blocos[inicio:fim]
        )

        # Aceita inclusive OCR ruim como
        # TITULOFLFITORAL.
        if "TITULO" in contexto:
            pontos += 70

        if "ELEITOR" in contexto:
            pontos += 30

        pontos += confianca(bloco) * 10

        candidatos.append(
            (pontos, numero, indice)
        )

    if not candidatos:
        return "", None

    candidatos.sort(
        key=lambda item: item[0],
        reverse=True
    )

    melhor = candidatos[0]

    return melhor[1], melhor[2]


# ============================================================
# NOME
# ============================================================

def parece_nome(valor):
    valor = limpar_texto(valor)

    if len(valor) < 7:
        return False

    if any(c.isdigit() for c in valor):
        return False

    letras = sum(c.isalpha() for c in valor)

    if letras < 7:
        return False

    normal = sem_acentos(valor)

    proibidos = [
        "REPUBLICA",
        "FEDERATIVA",
        "SECRETARIA",
        "SEGURANCA",
        "PUBLICA",
        "IDENTIFICACAO",
        "BIOMETRICA",
        "ELEITORAL",
        "TITULO",
        "CARTEIRA",
        "IDENTIDADE",
        "HABILITACAO",
        "NASCIMENTO",
        "VALIDADE",
        "EMISSAO",
        "ASSINATURA",
        "MUNICIPIO",
        "REGISTRO",
        "BRASIL",
        "ESTADO"
    ]

    if any(p in normal for p in proibidos):
        return False

    return True


def extrair_nome(blocos):
    candidatos = []

    for indice, bloco in enumerate(blocos):
        valor = texto(bloco)

        if not parece_nome(valor):
            continue

        pontos = confianca(bloco) * 20

        inicio = max(0, indice - 5)
        fim = min(len(blocos), indice + 3)

        contexto = " ".join(
            sem_acentos(texto(b))
            for b in blocos[inicio:fim]
        )

        if "NOME" in contexto:
            pontos += 60

        if "ELEITOR" in contexto:
            pontos += 30

        # Nome localizado dentro de região reconhecida
        # como título/identidade recebe reforço.
        if (
            "IDENTIFICACAO" in contexto
            or "BIOMETRICA" in contexto
        ):
            pontos += 20

        candidatos.append(
            (pontos, valor.upper())
        )

    if not candidatos:
        return ""

    candidatos.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return candidatos[0][1]


# ============================================================
# TELEFONE
# ============================================================

def formatar_telefone(numero):
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


def extrair_telefone(blocos, cpf, titulo):
    cpf_num = somente_numeros(cpf)
    titulo_num = somente_numeros(titulo)
    candidatos = []

    def adicionar(numero, valor, indice, bonus=0):
        if len(numero) not in (8, 9, 10, 11):
            return
        if numero in {cpf_num, titulo_num, ""}:
            return
        if len(numero) == 11 and cpf_valido(numero):
            return

        if len(numero) == 8:
            try:
                datetime.strptime(numero, "%d%m%Y")
                return
            except ValueError:
                pass

        inicio = max(0, indice - 4)
        fim = min(len(blocos), indice + 5)
        contexto = " ".join(sem_acentos(texto(b)) for b in blocos[inicio:fim])
        rotulo = any(t in contexto for t in
                     ["TELEFONE", "CELULAR", "FONE", "CONTATO", "WHATS"])

        pontos = confianca(blocos[indice]) * 10 + bonus
        if rotulo:
            pontos += 100
        if "-" in valor:
            pontos += 30
        if "(" in valor or ")" in valor:
            pontos += 25

        if len(numero) == 11 and numero[2] == "9":
            pontos += 65
        elif len(numero) == 10 and numero[2] in "2345":
            pontos += 30
        elif len(numero) == 9 and numero[0] == "9":
            pontos += 70
        elif len(numero) == 8 and numero[0] in "2345":
            pontos += 20
        else:
            pontos -= 40

        if any(t in contexto for t in [
            "CEP", "MATRICULA", "HIDROMETRO", "CONSUMO", "FATURA",
            "INSCRICAO", "CPF", "TITULO", "ZONA", "SECAO",
            "REGISTRO", "IDENTIDADE", "NASCIMENTO", "EMISSAO",
            "VALIDADE", "CNS", "CTPS"
        ]) and not rotulo:
            pontos -= 45

        if len(set(numero)) <= 3:
            pontos -= 30

        candidatos.append((pontos, numero))

    for i, bloco in enumerate(blocos):
        valor = texto(bloco)
        adicionar(somente_numeros(valor), valor, i)

    # Telefones manuscritos às vezes são quebrados em 2 ou 3 blocos.
    for i in range(len(blocos)):
        partes = []
        for j in range(i, min(i + 3, len(blocos))):
            bruto = texto(blocos[j])
            nums = somente_numeros(bruto)
            if not nums or len(nums) > 7:
                break

            if j > i:
                try:
                    a = blocos[j - 1]
                    b = blocos[j]
                    if a.get("pagina") != b.get("pagina"):
                        break
                    dx = abs(float(b["x_relativo"]) - float(a["x_relativo"]))
                    dy = abs(float(b["y_relativo"]) - float(a["y_relativo"]))
                    if dx > 0.18 or dy > 0.08:
                        break
                except Exception:
                    pass

            partes.append(nums)
            combinado = "".join(partes)
            if len(combinado) in (8, 9, 10, 11):
                valor_combinado = " ".join(texto(blocos[k]) for k in range(i, j + 1))
                adicionar(combinado, valor_combinado, i, bonus=20)

    if not candidatos:
        return ""

    candidatos.sort(key=lambda item: item[0], reverse=True)
    pontos, numero = candidatos[0]

    if pontos < 60:
        return ""

    return formatar_telefone(numero)


# ============================================================
# ZONA / SEÇÃO
# ============================================================

def extrair_zona_secao(blocos, indice_titulo):
    """
    Extrai ZONA e SEÇÃO sem depender de layout fixo.

    Estratégia:
    1) procura os rótulos ZONA e SEÇÃO em toda a página;
    2) aceita o número imediatamente antes OU depois do rótulo;
    3) dá preferência aos candidatos próximos ao TÍTULO ELEITORAL;
    4) evita confundir data, CPF, título e números longos.
    """

    def numero_curto(indice, max_digitos):
        if indice < 0 or indice >= len(blocos):
            return None

        valor = somente_numeros(texto(blocos[indice]))

        if not valor:
            return None

        if not (1 <= len(valor) <= max_digitos):
            return None

        return valor

    def distancia_titulo(indice):
        if indice_titulo is None:
            return 999
        return abs(indice - indice_titulo)

    zona_candidatos = []
    secao_candidatos = []

    # --------------------------------------------------------
    # 1) RÓTULOS EXPLÍCITOS
    # --------------------------------------------------------

    for indice, bloco in enumerate(blocos):
        normal = sem_acentos(texto(bloco))
        comp = compacto(texto(bloco))

        eh_zona = (
            normal == "ZONA"
            or "ZONA" in normal
            or comp == "ZONA"
        )

        eh_secao = (
            normal == "SECAO"
            or "SECAO" in normal
            or comp == "SECAO"
        )

        if eh_zona:
            # OCR pode devolver o valor antes ou depois do rótulo.
            for deslocamento in [-1, 1, -2, 2, -3, 3, -4, 4]:
                j = indice + deslocamento
                numero = numero_curto(j, 3)

                if numero is None:
                    continue

                pontos = 100
                pontos -= abs(deslocamento) * 8
                pontos -= distancia_titulo(j) * 2
                pontos += confianca(blocos[j]) * 10

                zona_candidatos.append(
                    (pontos, j, numero)
                )

        if eh_secao:
            for deslocamento in [-1, 1, -2, 2, -3, 3, -4, 4]:
                j = indice + deslocamento
                numero = numero_curto(j, 4)

                if numero is None:
                    continue

                pontos = 100
                pontos -= abs(deslocamento) * 8
                pontos -= distancia_titulo(j) * 2
                pontos += confianca(blocos[j]) * 10

                secao_candidatos.append(
                    (pontos, j, numero)
                )

    # --------------------------------------------------------
    # 2) FALLBACK: REGIÃO DO TÍTULO
    # --------------------------------------------------------
    # Em vários títulos o OCR reconhece:
    #
    # TITULO ...
    # nascimento
    # número do título
    # zona
    # seção
    #
    # mas pode falhar justamente nos rótulos.
    # Por isso analisamos números curtos perto do título.
    # --------------------------------------------------------

    if indice_titulo is not None:

        inicio = max(0, indice_titulo - 6)
        fim = min(len(blocos), indice_titulo + 10)

        curtos = []

        for j in range(inicio, fim):
            if j == indice_titulo:
                continue

            valor_original = texto(blocos[j])
            numero = somente_numeros(valor_original)

            if not numero:
                continue

            # Ignora datas e números longos.
            if "/" in valor_original:
                continue

            if 1 <= len(numero) <= 4:
                curtos.append(
                    (
                        j,
                        numero,
                        abs(j - indice_titulo),
                        confianca(blocos[j])
                    )
                )

        # Zona normalmente tem até 3 dígitos.
        if not zona_candidatos:
            for j, numero, distancia, conf in curtos:
                if len(numero) <= 3:
                    pontos = 40
                    pontos -= distancia * 3
                    pontos += conf * 10

                    zona_candidatos.append(
                        (pontos, j, numero)
                    )

        # Seção normalmente tem até 4 dígitos.
        if not secao_candidatos:
            for j, numero, distancia, conf in curtos:
                if len(numero) <= 4:
                    pontos = 35
                    pontos -= distancia * 3
                    pontos += conf * 10

                    secao_candidatos.append(
                        (pontos, j, numero)
                    )

    # --------------------------------------------------------
    # ESCOLHER MELHORES
    # --------------------------------------------------------

    zona = ""
    secao = ""
    indice_zona = None

    if zona_candidatos:
        zona_candidatos.sort(
            key=lambda item: item[0],
            reverse=True
        )

        _, indice_zona, zona = zona_candidatos[0]

    if secao_candidatos:
        # Evita usar exatamente o mesmo bloco escolhido como zona,
        # quando houver outro candidato plausível para seção.
        diferentes = [
            item
            for item in secao_candidatos
            if item[1] != indice_zona
        ]

        lista = (
            diferentes
            if diferentes
            else secao_candidatos
        )

        lista.sort(
            key=lambda item: item[0],
            reverse=True
        )

        _, _, secao = lista[0]

    # Mantém zeros à esquerda para a planilha.
    if zona:
        zona = zona.zfill(3)

    if secao:
        secao = secao.zfill(4)

    return zona, secao


# ============================================================
# RG
# ============================================================

def extrair_rg(blocos, cpf, titulo):
    proibidos = {
        somente_numeros(cpf),
        somente_numeros(titulo),
        ""
    }

    candidatos = []

    for indice, bloco in enumerate(blocos):
        valor = texto(bloco)
        numero = somente_numeros(valor)

        if not (6 <= len(numero) <= 10):
            continue

        if numero in proibidos:
            continue

        if len(numero) == 8:
            try:
                datetime.strptime(numero, "%d%m%Y")
                continue
            except ValueError:
                pass

        pontos = confianca(bloco) * 15

        inicio = max(0, indice - 8)
        fim = min(len(blocos), indice + 9)

        contexto = " ".join(
            sem_acentos(texto(b))
            for b in blocos[inicio:fim]
        )

        if "DOC IDENTIDADE" in contexto:
            pontos += 120

        if "REGISTRO GERAL" in contexto:
            pontos += 110

        if re.search(r"RG", contexto):
            pontos += 100

        if "IDENTIDADE" in contexto:
            pontos += 45

        if any(
            termo in contexto
            for termo in [
                "SSP",
                "SCJDS",
                "ORGAO EXPEDIDOR",
                "ORG EXPEDIDOR",
                "EXPEDIDOR"
            ]
        ):
            pontos += 45

        if 7 <= len(numero) <= 9:
            pontos += 25

        normal_valor = sem_acentos(valor)

        # Ex.: "31213766 SCJDS AL"
        if "SSP" in normal_valor or "SCJDS" in normal_valor:
            pontos += 80

        if any(
            termo in contexto
            for termo in [
                "CEP",
                "TELEFONE",
                "CELULAR",
                "FONE",
                "MATRICULA",
                "HIDROMETRO",
                "CONSUMO",
                "FATURA"
            ]
        ):
            pontos -= 50

        candidatos.append(
            (pontos, numero)
        )

    if not candidatos:
        return ""

    candidatos.sort(
        key=lambda item: item[0],
        reverse=True
    )

    if candidatos[0][0] < 55:
        return ""

    return candidatos[0][1]


# ============================================================
# NOME DA MÃE
# ============================================================

def _nome_filiacao_valido(valor, nome_principal):
    valor = limpar_texto(valor)
    if not parece_nome(valor):
        return False

    normal = sem_acentos(valor)
    if nome_principal and normal == sem_acentos(nome_principal):
        return False

    proibidos = [
        "RESPONSAVEL", "CLIENTE", "CPF", "CNPJ", "ENDERECO",
        "COMPANHIA", "SANEAMENTO", "CASAL", "FATURA", "CONSUMO",
        "VENCIMENTO", "MATRICULA", "HIDROMETRO", "ASSINATURA",
        "PORTADOR", "NACIONALIDADE", "VALIDADE", "NASCIMENTO",
        "IDENTIDADE", "REGISTRO", "ELEITORAL", "SECRETARIA",
        "REPUBLICA", "BRASILEIRO", "ORGAO", "EXPEDIDOR"
    ]
    if any(termo in normal for termo in proibidos):
        return False

    palavras = re.findall(r"[A-ZÀ-Ú]+", normal)
    return len(palavras) >= 2


def extrair_nome_mae(blocos, nome):
    # Primeiro procura NOME DA MÃE / MÃE.
    for indice, bloco in enumerate(blocos):
        normal = sem_acentos(texto(bloco))
        comp = compacto(texto(bloco))

        if not ("NOME DA MAE" in normal or "NOMEDAMAE" in comp or normal == "MAE"):
            continue

        for j in range(indice + 1, min(indice + 12, len(blocos))):
            candidato = texto(blocos[j])
            if _nome_filiacao_valido(candidato, nome):
                return candidato.upper()

    # Depois usa FILIAÇÃO sem depender de coordenada fixa.
    for indice, bloco in enumerate(blocos):
        comp = compacto(texto(bloco))
        if "FILIACAO" not in comp and "FILIACA" not in comp:
            continue

        nomes = []

        for j in range(indice + 1, min(indice + 22, len(blocos))):
            candidato = texto(blocos[j])
            normal = sem_acentos(candidato)

            if nomes and any(t in normal for t in [
                "ASSINATURA", "TITULO ELEITORAL", "NOME DO ELEITOR",
                "CPF/CNPJ", "ENDERECO DE ENTREGA", "OBSERVACOES"
            ]):
                break

            if not _nome_filiacao_valido(candidato, nome):
                continue

            candidato = candidato.upper()
            if sem_acentos(candidato) not in [sem_acentos(x) for x in nomes]:
                nomes.append(candidato)

            # Em CNH/RG, normalmente pai e mãe vêm nessa ordem.
            if len(nomes) >= 2:
                return nomes[1]

    return ""


# ============================================================
# ENDEREÇO
# ============================================================

def extrair_endereco(blocos):
    tipos = [
        "RUA ",
        "AVENIDA ",
        "AV ",
        "TRAVESSA ",
        "TV ",
        "RODOVIA ",
        "ESTRADA ",
        "SITIO ",
        "POVOADO ",
        "LOTEAMENTO ",
        "RESIDENCIAL ",
        "CONJUNTO ",
        "PRACA "
    ]

    for bloco in blocos:
        valor = texto(bloco)
        normal = sem_acentos(valor)

        if any(
            normal.startswith(tipo)
            for tipo in tipos
        ):
            return valor.upper()

    return ""


# ============================================================
# CIDADE
# ============================================================

def extrair_cidade(blocos):
    for bloco in blocos:
        valor = texto(bloco)
        normal = sem_acentos(valor)

        # Exemplos:
        # ARAPIRACA/AL
        # ARAPIRACA-AL
        match = re.search(
            r"\b([A-ZÀ-Ú][A-ZÀ-Ú\s]{2,})"
            r"[\-/]"
            r"([A-Z]{2})\b",
            valor.upper()
        )

        if match:
            cidade = limpar_texto(
                match.group(1)
            )

            if cidade:
                return cidade.upper()

        # OCR pode colar:
        # ARAPIRACAVAL
        if normal.endswith("AL") and len(normal) > 4:
            candidato = re.sub(
                r"[^A-Z]",
                "",
                normal
            )

            if candidato.endswith("AL"):
                candidato = candidato[:-2]

                # Evita palavras aleatórias.
                if len(candidato) >= 4:
                    return candidato

    return ""


# ============================================================
# EXTRATOR PRINCIPAL
# ============================================================


# ============================================================
# LEITURA POR RÓTULOS EXPLÍCITOS
# ============================================================

def _distancia(a, b):
    try:
        ax, ay = float(a["x_relativo"]), float(a["y_relativo"])
        bx, by = float(b["x_relativo"]), float(b["y_relativo"])
        return ((ax-bx)**2 + (ay-by)**2) ** 0.5
    except Exception:
        return 999.0


def _eh_rotulo(valor):
    n = sem_acentos(valor)
    c = compacto(valor)
    termos = [
        "NOME DO ELEITOR", "NOMEDOELEITOR", "DATA DE NASCIMENTO",
        "DATADENASCIMENTO", "INSCRICAO", "ZONA", "SECAO", "MUNICIPIO",
        "FILIACAO", "CODIGO DE VALIDACAO", "CODIGODEVALIDACAO",
        "DATA DE EMISSAO", "JUSTICA ELEITORAL", "REPUBLICA FEDERATIVA",
        "TITULO ELEITORAL"
    ]
    return any(t in n or t in c for t in termos)


def _nome_forte(valor):
    valor = limpar_texto(valor)
    if not parece_nome(valor) or _eh_rotulo(valor):
        return False
    n = sem_acentos(valor)
    proibidos = [
        "CODIGO", "VALIDACAO", "JUSTICA", "ELEITORAL", "REPUBLICA",
        "FEDERATIVA", "BRASIL", "ORIENTACOES", "TRIBUNAL", "INTERNET",
        "MUNICIPIO", "BIOMETRIA", "ELEITOR", "ELEITORA", "TITULO"
    ]
    return not any(p in n for p in proibidos)


def _perto(blocos, i, limite):
    r = blocos[i]
    itens = []
    for j, b in enumerate(blocos):
        if j == i or b.get("pagina") != r.get("pagina"):
            continue
        d = _distancia(r, b)
        if d <= limite:
            itens.append((d, j, b))
    return sorted(itens, key=lambda x: x[0])


def extrair_nome_rotulado(blocos):
    for i, b in enumerate(blocos):
        n, c = sem_acentos(texto(b)), compacto(texto(b))
        if "NOME DO ELEITOR" not in n and "NOMEDOELEITOR" not in c:
            continue
        candidatos = []
        for d, _, cand in _perto(blocos, i, 0.16):
            v = limpar_texto(texto(cand))
            if _nome_forte(v):
                candidatos.append((100 - d*200, v.upper()))
        if candidatos:
            return max(candidatos)[1]
    return ""


def extrair_cidade_rotulada(blocos):
    for i, b in enumerate(blocos):
        n = sem_acentos(texto(b))
        if "MUNICIPIO" not in n:
            continue
        candidatos = []
        for d, _, cand in _perto(blocos, i, 0.15):
            v = limpar_texto(texto(cand)).upper()
            vn = sem_acentos(v)
            if _eh_rotulo(v) or any(x in vn for x in ["CODIGO","VALIDACAO","JUSTICA","ELEITORAL"]):
                continue
            m = re.match(r"^\s*([A-ZÀ-Ú][A-ZÀ-Ú\s.'-]{2,}?)(?:\s*[/\-]\s*[A-Z]{2})?\s*$", v)
            if m:
                cidade = limpar_texto(m.group(1)).strip(" -/")
                if len(cidade) >= 3:
                    candidatos.append((100-d*200, cidade))
        if candidatos:
            return max(candidatos)[1]
    return ""


def extrair_zona_secao_rotuladas(blocos):
    saida = {"ZONA": "", "SEÇÃO": ""}
    for chave, termo in [("ZONA","ZONA"), ("SEÇÃO","SECAO")]:
        melhores = []
        for i, b in enumerate(blocos):
            if termo not in sem_acentos(texto(b)):
                continue
            for d, _, cand in _perto(blocos, i, 0.09):
                bruto = limpar_texto(texto(cand))
                num = somente_numeros(bruto)
                if not num or len(num) > 4:
                    continue
                # bloco deve ser essencialmente numérico
                if len(num) < max(1, len(bruto.replace(" ","")) - 1):
                    continue
                pontos = 100-d*300
                try:
                    dx = abs(float(cand["x_relativo"])-float(b["x_relativo"]))
                    if dx < 0.055:
                        pontos += 35
                except Exception:
                    pass
                melhores.append((pontos, num))
        if melhores:
            valor = max(melhores)[1]
            saida[chave] = valor.zfill(3 if chave=="ZONA" else 4)
    return saida["ZONA"], saida["SEÇÃO"]


def extrair_mae_filiacao_rotulada(blocos, nome_principal):
    for i, b in enumerate(blocos):
        c = compacto(texto(b))
        if "FILIACAO" not in c and "FILIACA" not in c:
            continue

        candidatos = []
        for d, j, cand in _perto(blocos, i, 0.20):
            v = limpar_texto(texto(cand))
            if not _nome_filiacao_valido(v, nome_principal):
                continue
            try:
                y = float(cand["y_relativo"])
                x = float(cand["x_relativo"])
            except Exception:
                y, x = 9.0, 9.0
            candidatos.append((y, x, d, v.upper()))

        if candidatos:
            # Título eleitoral não informa "pai/mãe"; no modelo testado,
            # o primeiro nome visual da filiação é a mãe.
            candidatos.sort(key=lambda z: (z[0], z[1]))
            return candidatos[0][3]
    return ""


def extrair_dados_motor_vscode(blocos, recuperados=None):

    # Segurança: garante que estamos usando a versão correta.
    if blocos and not isinstance(blocos[0], dict):
        raise TypeError(
            "O extrator V2 esperava blocos do RapidOCR, "
            "mas recebeu textos simples."
        )

    nome = extrair_nome(blocos)

    cpf = extrair_cpf(blocos)

    nascimento = extrair_nascimento(
        blocos
    )

    titulo, indice_titulo = extrair_titulo(
        blocos
    )

    zona, secao = extrair_zona_secao(
        blocos,
        indice_titulo
    )

    rg = extrair_rg(
        blocos,
        cpf,
        titulo
    )

    nome_mae = extrair_nome_mae(
        blocos,
        nome
    )

    telefone = extrair_telefone(
        blocos,
        cpf,
        titulo
    )

    endereco = extrair_endereco(
        blocos
    )

    cidade = extrair_cidade(
        blocos
    )

    # Rótulos explícitos têm prioridade sobre heurísticas genéricas.
    nome_rotulo = extrair_nome_rotulado(blocos)
    if nome_rotulo:
        nome = nome_rotulo

    cidade_rotulo = extrair_cidade_rotulada(blocos)
    if cidade_rotulo:
        cidade = cidade_rotulo

    zona_rotulo, secao_rotulo = extrair_zona_secao_rotuladas(blocos)
    if zona_rotulo:
        zona = zona_rotulo
    if secao_rotulo:
        secao = secao_rotulo

    mae_rotulo = extrair_mae_filiacao_rotulada(blocos, nome)
    if mae_rotulo:
        nome_mae = mae_rotulo

    recuperados = recuperados or {}

    mae_recuperada = limpar_texto(
        recuperados.get("NOME DA MÃE", "")
    )
    telefone_recuperado = limpar_texto(
        recuperados.get("TELEFONE", "")
    )

    if mae_recuperada:
        nome_mae = mae_recuperada.upper()

    if telefone_recuperado:
        telefone = telefone_recuperado

    return {
        "NOME": nome,
        "CPF": cpf,
        "RG": rg,
        "DATA DE NASCIMENTO": nascimento,
        "NOME DA MÃE": nome_mae,

        "ENDEREÇO": endereco,
        "Nº": "",
        "BAIRRO": "",
        "CIDADE": cidade,

        "TITULO": titulo,
        "ZONA": zona,
        "SEÇÃO": secao,

        "TELEFONE": telefone
    }

# ============================================================
# 23. EXTRAIR DADOS OCR
# ============================================================

def extrair_dados_ocr(
    texto,
    itens
):
    dados = extrair_dados_motor_vscode(itens)

    return {
        "nome": dados.get("NOME", ""),
        "cpf": dados.get("CPF", ""),
        "rg": dados.get("RG", ""),
        "data_nascimento": dados.get("DATA DE NASCIMENTO", ""),
        "nome_mae": dados.get("NOME DA MÃE", ""),
        "endereco": dados.get("ENDEREÇO", ""),
        "numero": dados.get("Nº", ""),
        "bairro": dados.get("BAIRRO", ""),
        "cidade": dados.get("CIDADE", ""),
        "titulo": dados.get("TITULO", ""),
        "zona": dados.get("ZONA", ""),
        "secao": dados.get("SEÇÃO", ""),
        "telefone": dados.get("TELEFONE", ""),
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
