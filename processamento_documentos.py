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


def _analisar_box(box):
    if box is None:
        return None

    try:
        pontos = [(float(p[0]), float(p[1])) for p in box]
        xs = [p[0] for p in pontos]
        ys = [p[1] for p in pontos]

        return {
            "x_min": min(xs),
            "y_min": min(ys),
            "x_max": max(xs),
            "y_max": max(ys),
            "centro_x": (min(xs) + max(xs)) / 2,
            "centro_y": (min(ys) + max(ys)) / 2,
        }
    except Exception:
        return None


def executar_ocr_imagem(imagem, pagina=1):
    """
    RapidOCR com a mesma estrutura geométrica usada no teste do VSCode.
    Além de x/y, preserva página, dimensões e coordenadas relativas.
    """
    imagem = preparar_imagem(imagem)
    largura, altura = imagem.size

    resultado = obter_rapidocr()(np.array(imagem))

    textos = getattr(resultado, "txts", None) or []
    scores = getattr(resultado, "scores", None) or []
    boxes = getattr(resultado, "boxes", None) or []

    itens = []

    for i, texto_bruto in enumerate(textos):
        valor = str(texto_bruto or "").strip()
        if not valor:
            continue

        conf = 0.0
        if i < len(scores):
            try:
                conf = float(scores[i])
            except Exception:
                pass

        box = boxes[i] if i < len(boxes) else None
        pos = _analisar_box(box)

        item = {
            "texto": valor,
            "confianca": conf,
            "pagina": pagina,
            "largura_pagina": largura,
            "altura_pagina": altura,
            "box": box,
            "x_min": None,
            "y_min": None,
            "x_max": None,
            "y_max": None,
            "centro_x": None,
            "centro_y": None,
            "x_relativo": None,
            "y_relativo": None,
            # Compatibilidade com o restante do Streamlit
            "x": 0.0,
            "y": 0.0,
        }

        if pos:
            item.update(pos)
            item["x"] = pos["centro_x"]
            item["y"] = pos["centro_y"]
            item["x_relativo"] = pos["centro_x"] / largura if largura else None
            item["y_relativo"] = pos["centro_y"] / altura if altura else None

        itens.append(item)

    # Não destrói a estrutura espacial; apenas mantém uma ordem estável de leitura.
    itens.sort(key=lambda item: (
        item["pagina"],
        round((item["y_relativo"] or 0) / 0.006),
        item["x_relativo"] or 0
    ))

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
            "png"
        )

        imagem = Image.open(
            io.BytesIO(
                bytes_imagem
            )
        ).convert(
            "RGB"
        )

        texto, itens = executar_ocr_imagem(
            imagem,
            pagina=numero_pagina + 1
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
    1) prioriza MÃE/NOME DA MÃE explícito;
    2) no título eleitoral, usa FILIAÇÃO + posição visual,
       como na versão do VSCode que acertou o nome da mãe.
    """
    rotulos_mae = []

    for item in itens:
        rotulo = normalizar_rotulo(item.get("texto", ""))
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

            candidato = str(item.get("texto", "") or "").strip()

            if not parece_nome(candidato):
                continue

            dx = abs(float(item.get("x", 0)) - float(rotulo.get("x", 0)))
            dy = float(item.get("y", 0)) - float(rotulo.get("y", 0))

            if -50 <= dy <= 230 and dx <= 750:
                candidatos.append(
                    (
                        abs(dy) + dx * 0.2,
                        -float(item.get("confianca", 0) or 0),
                        candidato.upper()
                    )
                )

        if candidatos:
            candidatos.sort()
            return candidatos[0][2]

    # FILIAÇÃO: reproduz a leitura espacial que funcionou no VSCode.
    for i, bloco in enumerate(itens):
        rotulo = normalizar_rotulo(bloco.get("texto", ""))

        if "FILIACAO" not in rotulo and "FILIACA" not in rotulo:
            continue

        candidatos = []

        for distancia, _, candidato in _itens_perto(itens, i, 0.20):
            valor = str(candidato.get("texto", "") or "").strip()

            if not parece_nome(valor):
                continue

            normal = remover_acentos(valor).upper()

            if any(termo in normal for termo in [
                "ASSINATURA", "ELEITORAL", "VALIDACAO", "JUSTICA",
                "REPUBLICA", "MUNICIPIO", "NASCIMENTO", "EMISSAO"
            ]):
                continue

            try:
                y = float(candidato["y_relativo"])
                x = float(candidato["x_relativo"])
            except Exception:
                continue

            candidatos.append((y, x, distancia, valor.upper()))

        if candidatos:
            candidatos.sort(key=lambda item: (item[0], item[1]))
            return candidatos[0][3]

    return ""


# ============================================================
# 22. ZONA E SEÇÃO OCR
# ============================================================

def _distancia_relativa(a, b):
    try:
        ax = float(a.get("x_relativo"))
        ay = float(a.get("y_relativo"))
        bx = float(b.get("x_relativo"))
        by = float(b.get("y_relativo"))
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
    except Exception:
        return 999.0


def _itens_perto(itens, indice, limite):
    referencia = itens[indice]
    proximos = []

    for j, candidato in enumerate(itens):
        if j == indice:
            continue

        if candidato.get("pagina") != referencia.get("pagina"):
            continue

        distancia = _distancia_relativa(referencia, candidato)

        if distancia <= limite:
            proximos.append((distancia, j, candidato))

    return sorted(proximos, key=lambda item: item[0])


def encontrar_zona_secao_ocr(itens, titulo):
    """
    Mesma estratégia espacial que acertou 055 / 0252 no teste do VSCode:
    procura ZONA/SEÇÃO e escolhe o número curto geometricamente mais próximo.
    """
    saida = {"ZONA": "", "SECAO": ""}

    for chave, termo, max_digitos in [
        ("ZONA", "ZONA", 3),
        ("SECAO", "SECAO", 4),
    ]:
        melhores = []

        for i, bloco in enumerate(itens):
            rotulo = normalizar_rotulo(bloco.get("texto", ""))

            if termo not in rotulo:
                continue

            for distancia, _, candidato in _itens_perto(itens, i, 0.09):
                bruto = str(candidato.get("texto", "") or "").strip()

                # Data não pode virar zona/seção.
                if re.search(r"\d{1,2}[\/.\-]\d{1,2}[\/.\-]\d{4}", bruto):
                    continue

                numero = somente_numeros(bruto)

                if not numero or len(numero) > max_digitos:
                    continue

                if numero == somente_numeros(titulo):
                    continue

                # O bloco precisa ser essencialmente numérico.
                compactado = re.sub(r"\s+", "", bruto)
                if len(numero) < max(1, len(compactado) - 1):
                    continue

                pontos = 100 - distancia * 300

                try:
                    dx = abs(
                        float(candidato["x_relativo"])
                        - float(bloco["x_relativo"])
                    )
                    if dx < 0.055:
                        pontos += 35
                except Exception:
                    pass

                pontos += float(candidato.get("confianca", 0) or 0) * 5
                melhores.append((pontos, numero))

        if melhores:
            melhores.sort(key=lambda item: item[0], reverse=True)
            saida[chave] = melhores[0][1]

    zona = saida["ZONA"].zfill(3) if saida["ZONA"] else ""
    secao = saida["SECAO"].zfill(4) if saida["SECAO"] else ""

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
