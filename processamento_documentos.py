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

    textos = getattr(resultado, "txts", None)
    scores = getattr(resultado, "scores", None)
    boxes = getattr(resultado, "boxes", None)

    if textos is None:
        textos = []
    if scores is None:
        scores = []
    if boxes is None:
        boxes = []

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

    # Mesma ordem recebida do RapidOCR no teste do VSCode.
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
    """Extrai mãe por rótulos semânticos, sem layout fixo."""
    rotulos_mae=("MAE","NOMEDAMAE","NOMEMAE","MOTHER","MOTHERSNAME")
    for i,linha in enumerate(linhas):
        r=normalizar_rotulo(linha)
        if r in rotulos_mae or "NOMEDAMAE" in r or "MOTHERSNAME" in r:
            for d in (1,2,3,-1):
                j=i+d
                if 0<=j<len(linhas) and parece_nome(linhas[j]): return linhas[j].upper()
    total=" ".join(remover_acentos(x).upper() for x in linhas)
    eleitoral=any(t in total for t in ("ELEITOR","JUSTICA ELEITORAL","TITULO ELEITORAL"))
    for i,linha in enumerate(linhas):
        r=normalizar_rotulo(linha)
        if not ("FILIACAO" in r or "FILIATION" in r or "PARENTAGE" in r or r=="PARENTS"): continue
        nomes=[]
        for j in range(i+1,min(i+10,len(linhas))):
            v=linhas[j].strip()
            if parece_nome(v) and not re.search(r"[/\-]\s*[A-Z]{2}$",v.upper()):
                if remover_acentos(v).upper() not in [remover_acentos(x).upper() for x in nomes]: nomes.append(v.upper())
            if len(nomes)>=2: break
        if nomes: return nomes[0] if eleitoral or len(nomes)==1 else nomes[1]
    return ""


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
            "NOMEDAELEITORA",
            "NOME",
            "NOMECOMPLETO",
            "NAME",
            "FULLNAME"
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
        textos = getattr(resultado, "txts", None)
        scores = getattr(resultado, "scores", None)
        boxes = getattr(resultado, "boxes", None)

        # RapidOCR pode devolver numpy.ndarray. Não usar `or []`,
        # porque array NumPy com vários elementos não pode ser avaliado
        # diretamente como True/False.
        if textos is None:
            textos = []
        if scores is None:
            scores = []
        if boxes is None:
            boxes = []

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
# MOTOR COMPLETO DO VSCODE - ISOLADO
# ============================================================

_MOTOR_VSCODE = {}
exec('import re\nimport unicodedata\nfrom datetime import datetime\n\n\n# ============================================================\n# UTILIDADES\n# ============================================================\n\ndef limpar_texto(valor):\n    if valor is None:\n        return ""\n    return re.sub(r"\\s+", " ", str(valor)).strip()\n\n\ndef sem_acentos(valor):\n    valor = limpar_texto(valor)\n\n    return "".join(\n        c for c in unicodedata.normalize("NFD", valor)\n        if unicodedata.category(c) != "Mn"\n    ).upper()\n\n\ndef somente_numeros(valor):\n    return re.sub(r"\\D", "", limpar_texto(valor))\n\n\ndef texto(bloco):\n    """\n    IMPORTANTE:\n    Agora o extrator recebe os dicionários criados\n    pelo teste_ocr.py.\n    """\n    if isinstance(bloco, dict):\n        return limpar_texto(bloco.get("texto", ""))\n\n    return limpar_texto(bloco)\n\n\ndef confianca(bloco):\n    if not isinstance(bloco, dict):\n        return 0.0\n\n    try:\n        return float(bloco.get("confianca") or 0)\n    except Exception:\n        return 0.0\n\n\n# ============================================================\n# NORMALIZAÇÃO PARA COMPARAR RÓTULOS\n# ============================================================\n\ndef compacto(valor):\n    return re.sub(\n        r"[^A-Z0-9]",\n        "",\n        sem_acentos(valor)\n    )\n\n\ndef contem_algum(valor, termos):\n    normal = sem_acentos(valor)\n    comp = compacto(valor)\n\n    for termo in termos:\n        termo_normal = sem_acentos(termo)\n        termo_comp = compacto(termo)\n\n        if termo_normal in normal:\n            return True\n\n        if len(termo_comp) >= 5 and termo_comp in comp:\n            return True\n\n    return False\n\n\n# ============================================================\n# CPF\n# ============================================================\n\ndef cpf_valido(numero):\n    numero = somente_numeros(numero)\n\n    if len(numero) != 11:\n        return False\n\n    if numero == numero[0] * 11:\n        return False\n\n    try:\n        soma = sum(\n            int(numero[i]) * (10 - i)\n            for i in range(9)\n        )\n\n        resto = soma % 11\n        d1 = 0 if resto < 2 else 11 - resto\n\n        soma = sum(\n            int(numero[i]) * (11 - i)\n            for i in range(10)\n        )\n\n        resto = soma % 11\n        d2 = 0 if resto < 2 else 11 - resto\n\n        return numero[-2:] == f"{d1}{d2}"\n\n    except Exception:\n        return False\n\n\ndef formatar_cpf(numero):\n    numero = somente_numeros(numero)\n\n    return (\n        f"{numero[:3]}."\n        f"{numero[3:6]}."\n        f"{numero[6:9]}-"\n        f"{numero[9:]}"\n    )\n\n\ndef extrair_cpf(blocos):\n    # Primeiro: CPF matematicamente válido.\n    for bloco in blocos:\n        numero = somente_numeros(texto(bloco))\n\n        if len(numero) == 11 and cpf_valido(numero):\n            return formatar_cpf(numero)\n\n    # Segundo: número de 11 dígitos explicitamente\n    # associado a CPF.\n    for i, bloco in enumerate(blocos):\n        if not contem_algum(texto(bloco), ["CPF"]):\n            continue\n\n        for j in range(i, min(i + 4, len(blocos))):\n            numero = somente_numeros(texto(blocos[j]))\n\n            if len(numero) == 11:\n                return formatar_cpf(numero)\n\n    return ""\n\n\n# ============================================================\n# DATA DE NASCIMENTO\n# ============================================================\n\nPADRAO_DATA = re.compile(\n    r"\\b"\n    r"(0?[1-9]|[12]\\d|3[01])"\n    r"[\\/\\-.]"\n    r"(0?[1-9]|1[0-2])"\n    r"[\\/\\-.]"\n    r"((?:19|20)\\d{2})"\n    r"\\b"\n)\n\n\ndef extrair_datas(valor):\n    encontrados = []\n\n    for match in PADRAO_DATA.finditer(texto(valor)):\n        dia = int(match.group(1))\n        mes = int(match.group(2))\n        ano = int(match.group(3))\n\n        try:\n            data = datetime(ano, mes, dia)\n            encontrados.append(data)\n        except ValueError:\n            pass\n\n    return encontrados\n\n\ndef extrair_nascimento(blocos):\n    candidatos = []\n\n    ano_atual = datetime.now().year\n\n    for indice, bloco in enumerate(blocos):\n        for data in extrair_datas(bloco):\n\n            pontos = 0\n\n            idade = ano_atual - data.year\n\n            # Cadastro de adulto: forte indício.\n            if 16 <= idade <= 110:\n                pontos += 40\n            elif 0 <= idade <= 110:\n                pontos += 10\n\n            # Confiança do OCR.\n            pontos += confianca(bloco) * 10\n\n            # Procura contexto próximo na ORDEM do OCR.\n            inicio = max(0, indice - 4)\n            fim = min(len(blocos), indice + 5)\n\n            contexto = " ".join(\n                sem_acentos(texto(b))\n                for b in blocos[inicio:fim]\n            )\n\n            if any(\n                marcador in contexto\n                for marcador in [\n                    "NASCIMENTO",\n                    "NASC",\n                    "NASCIME",\n                    "DATA DE NASC"\n                ]\n            ):\n                pontos += 60\n\n            if any(\n                marcador in contexto\n                for marcador in [\n                    "EMISSAO",\n                    "VALIDADE",\n                    "EXPEDICAO"\n                ]\n            ):\n                pontos -= 30\n\n            candidatos.append(\n                (pontos, data)\n            )\n\n    if not candidatos:\n        return ""\n\n    candidatos.sort(\n        key=lambda item: item[0],\n        reverse=True\n    )\n\n    return candidatos[0][1].strftime("%d/%m/%Y")\n\n\n# ============================================================\n# TÍTULO ELEITORAL\n# ============================================================\n\ndef extrair_titulo(blocos):\n    """\n    Extrai título eleitoral sem depender de posição/layout fixo.\n\n    Aceita:\n    - 12 dígitos no mesmo bloco;\n    - grupos fragmentados em vários blocos;\n    - separadores/espaços/pontos;\n    - confusões OCR comuns (O->0, I/L->1, B->8, S->5, Z->2, G->6)\n      SOMENTE quando o contexto é eleitoral.\n\n    INSCRIÇÃO ajuda na pontuação, mas NÃO é obrigatória.\n    """\n\n    def normalizar_numero_eleitoral(valor):\n        bruto = str(valor or "").upper().strip()\n\n        # Mantém somente caracteres que podem representar número\n        # em uma leitura OCR degradada.\n        limpo = re.sub(r"[^0-9OILBSZG]", "", bruto)\n\n        tabela = str.maketrans({\n            "O": "0",\n            "I": "1",\n            "L": "1",\n            "B": "8",\n            "S": "5",\n            "Z": "2",\n            "G": "6",\n        })\n\n        return limpo.translate(tabela)\n\n    def contexto_eleitoral(inicio, fim):\n        return " ".join(\n            sem_acentos(texto(b))\n            for b in blocos[max(0, inicio):min(len(blocos), fim)]\n        )\n\n    def pontuar_contexto(ctx):\n        pontos = 0\n\n        if "INSCRICAO" in ctx:\n            pontos += 100\n        if "TITULO" in ctx:\n            pontos += 90\n        if "ELEITOR" in ctx:\n            pontos += 55\n        if "ZONA" in ctx:\n            pontos += 30\n        if "SECAO" in ctx:\n            pontos += 30\n        if "JUIZ ELEITORAL" in ctx:\n            pontos += 25\n        if "JUSTICA ELEITORAL" in ctx:\n            pontos += 25\n\n        return pontos\n\n    candidatos = []\n\n    # --------------------------------------------------------\n    # 1) UM ÚNICO BLOCO\n    # --------------------------------------------------------\n    for indice, bloco in enumerate(blocos):\n        valor = texto(bloco)\n\n        numero_puro = somente_numeros(valor)\n        ctx = contexto_eleitoral(indice - 12, indice + 7)\n        bonus_ctx = pontuar_contexto(ctx)\n\n        # Primeiro tenta sem nenhuma correção OCR.\n        if len(numero_puro) == 12:\n            pontos = 40 + bonus_ctx\n            pontos += confianca(bloco) * 10\n\n            if len(valor.split()) >= 2:\n                pontos += 10\n\n            candidatos.append((pontos, numero_puro, indice))\n\n        # Correção de caracteres só é permitida se houver contexto eleitoral.\n        if bonus_ctx >= 30:\n            corrigido = normalizar_numero_eleitoral(valor)\n\n            if len(corrigido) == 12 and corrigido != numero_puro:\n                pontos = 30 + bonus_ctx\n                pontos += confianca(bloco) * 8\n                # Pequena penalidade porque houve correção OCR.\n                pontos -= 8\n\n                candidatos.append((pontos, corrigido, indice))\n\n    # --------------------------------------------------------\n    # 2) VÁRIOS BLOCOS / INSCRIÇÃO FRAGMENTADA\n    # --------------------------------------------------------\n    for i in range(len(blocos)):\n        partes = []\n        indices = []\n        houve_correcao = False\n\n        ctx_pre = contexto_eleitoral(i - 12, i + 10)\n        bonus_pre = pontuar_contexto(ctx_pre)\n\n        # Sem contexto eleitoral mínimo, não fazemos correções letra->número.\n        permite_correcao = bonus_pre >= 30\n\n        for j in range(i, min(i + 9, len(blocos))):\n            bruto = texto(blocos[j])\n            normal = sem_acentos(bruto)\n\n            # Rótulos podem estar intercalados e não fazem parte do número.\n            if any(r in normal for r in [\n                "INSCRICAO", "TITULO", "ELEITOR"\n            ]):\n                continue\n\n            # Esses rótulos delimitam outros campos. Se já começamos\n            # a montar o número, encerramos para não anexar zona/seção/data.\n            if any(r in normal for r in [\n                "ZONA", "SECAO", "NASCIMENTO", "EMISSAO",\n                "VALIDADE", "CPF", "RG", "MUNICIPIO"\n            ]):\n                if partes:\n                    break\n                continue\n\n            puro = somente_numeros(bruto)\n            parte = puro\n\n            if permite_correcao:\n                corrigida = normalizar_numero_eleitoral(bruto)\n                # Só usa a versão corrigida quando ela realmente acrescenta\n                # informação plausível ao fragmento.\n                if corrigida and len(corrigida) >= len(puro):\n                    parte = corrigida\n                    if corrigida != puro:\n                        houve_correcao = True\n\n            # Fragmentos de título normalmente têm poucos dígitos.\n            if parte and 1 <= len(parte) <= 8:\n                partes.append(parte)\n                indices.append(j)\n\n                combinado = "".join(partes)\n\n                if len(combinado) == 12:\n                    ctx = contexto_eleitoral(i - 12, j + 7)\n                    bonus_ctx = pontuar_contexto(ctx)\n\n                    # Exige evidência eleitoral para uma composição.\n                    if bonus_ctx >= 30:\n                        pontos = 45 + bonus_ctx\n                        pontos -= max(0, len(partes) - 1) * 4\n\n                        if houve_correcao:\n                            pontos -= 10\n\n                        confs = [confianca(blocos[k]) for k in indices]\n                        if confs:\n                            pontos += (sum(confs) / len(confs)) * 8\n\n                        candidatos.append((pontos, combinado, i))\n                    break\n\n                if len(combinado) > 12:\n                    break\n\n            elif partes:\n                # Tolera ruído curto; texto longo encerra a sequência.\n                if len(bruto.strip()) > 4:\n                    break\n\n    if not candidatos:\n        return "", None\n\n    # Remove duplicatas, mantendo a maior pontuação de cada número.\n    melhores = {}\n    for pontos, numero, indice in candidatos:\n        atual = melhores.get(numero)\n        if atual is None or pontos > atual[0]:\n            melhores[numero] = (pontos, indice)\n\n    finais = [\n        (pontos, numero, indice)\n        for numero, (pontos, indice) in melhores.items()\n    ]\n\n    finais.sort(key=lambda item: item[0], reverse=True)\n    melhor = finais[0]\n\n    return melhor[1], melhor[2]\n\n\n# ============================================================\n# NOME\n# ============================================================\n\ndef parece_nome(valor):\n    valor = limpar_texto(valor)\n\n    if len(valor) < 7:\n        return False\n\n    if any(c.isdigit() for c in valor):\n        return False\n\n    letras = sum(c.isalpha() for c in valor)\n\n    if letras < 7:\n        return False\n\n    normal = sem_acentos(valor)\n\n    proibidos = [\n        "REPUBLICA",\n        "FEDERATIVA",\n        "SECRETARIA",\n        "SEGURANCA",\n        "PUBLICA",\n        "IDENTIFICACAO",\n        "BIOMETRICA",\n        "ELEITORAL",\n        "TITULO",\n        "CARTEIRA",\n        "IDENTIDADE",\n        "HABILITACAO",\n        "NASCIMENTO",\n        "VALIDADE",\n        "EMISSAO",\n        "ASSINATURA",\n        "MUNICIPIO",\n        "REGISTRO",\n        "BRASIL",\n        "ESTADO"\n    ]\n\n    if any(p in normal for p in proibidos):\n        return False\n\n    return True\n\n\ndef extrair_nome(blocos):\n    """Extrai nome por rótulo e contexto, sem coordenada fixa."""\n    def rotulo(v):\n        n,c=sem_acentos(v),compacto(v)\n        return n in {"NOME","NAME","FULL NAME","NOME COMPLETO","NOME DO ELEITOR","NOME DA ELEITORA"} or c in {"NOME","NAME","FULLNAME","NOMECOMPLETO","NOMEDOELEITOR","NOMEDAELEITORA"}\n    def valido(v):\n        if not parece_nome(v): return False\n        n=sem_acentos(v)\n        if re.search(r"[/\\-]\\s*[A-Z]{2}\\s*$",v.upper()): return False\n        return not any(x in n for x in ["FILIACAO","FILIATION","MUNICIPIO","CIDADE","CODIGO","VALIDACAO","JUSTICA","ELEITORAL","BIOMETRIA","BIOMETRICA","COLETADA","COLETADO","ELEITOR/ELEITORA","ELEITOR ELEITORA","STATUS"])\n    for i,b in enumerate(blocos):\n        if not rotulo(texto(b)): continue\n        cs=[]\n        for j in range(i+1,min(i+9,len(blocos))):\n            v=texto(blocos[j])\n            if valido(v): cs.append((220-(j-i)*12+confianca(blocos[j])*20+min(len(v.split()),6)*4,v.upper()))\n        if cs: return max(cs,key=lambda x:x[0])[1]\n    cs=[]\n    for i,b in enumerate(blocos):\n        v=texto(b)\n        if not valido(v): continue\n        ctx=" ".join(sem_acentos(texto(x)) for x in blocos[max(0,i-6):min(len(blocos),i+4)])\n        p=confianca(b)*20+min(len(v.split()),6)*5\n        if "NOME" in ctx or "NAME" in ctx: p+=70\n        if "ELEITOR" in ctx: p+=25\n        if "IDENTIFICACAO" in ctx or "BIOMETRICA" in ctx: p+=15\n        cs.append((p,v.upper()))\n    return max(cs,key=lambda x:x[0])[1] if cs else ""\n\n\ndef formatar_telefone(numero):\n    numero = somente_numeros(numero)\n    if len(numero) == 11:\n        return f"({numero[:2]}) {numero[2:7]}-{numero[7:]}"\n    if len(numero) == 10:\n        return f"({numero[:2]}) {numero[2:6]}-{numero[6:]}"\n    if len(numero) == 9:\n        return f"{numero[:5]}-{numero[5:]}"\n    if len(numero) == 8:\n        return f"{numero[:4]}-{numero[4:]}"\n    return numero\n\n\ndef extrair_telefone(blocos, cpf, titulo):\n    cpf_num = somente_numeros(cpf)\n    titulo_num = somente_numeros(titulo)\n    candidatos = []\n\n    def adicionar(numero, valor, indice, bonus=0):\n        if len(numero) not in (8, 9, 10, 11):\n            return\n        if numero in {cpf_num, titulo_num, ""}:\n            return\n        if len(numero) == 11 and cpf_valido(numero):\n            return\n\n        if len(numero) == 8:\n            try:\n                datetime.strptime(numero, "%d%m%Y")\n                return\n            except ValueError:\n                pass\n\n        inicio = max(0, indice - 4)\n        fim = min(len(blocos), indice + 5)\n        contexto = " ".join(sem_acentos(texto(b)) for b in blocos[inicio:fim])\n        rotulo = any(t in contexto for t in\n                     ["TELEFONE", "CELULAR", "FONE", "CONTATO", "WHATS"])\n\n        pontos = confianca(blocos[indice]) * 10 + bonus\n        if rotulo:\n            pontos += 100\n        if "-" in valor:\n            pontos += 30\n        if "(" in valor or ")" in valor:\n            pontos += 25\n\n        if len(numero) == 11 and numero[2] == "9":\n            pontos += 65\n        elif len(numero) == 10 and numero[2] in "2345":\n            pontos += 30\n        elif len(numero) == 9 and numero[0] == "9":\n            pontos += 70\n        elif len(numero) == 8 and numero[0] in "2345":\n            pontos += 20\n        else:\n            pontos -= 40\n\n        if any(t in contexto for t in [\n            "CEP", "MATRICULA", "HIDROMETRO", "CONSUMO", "FATURA",\n            "INSCRICAO", "CPF", "TITULO", "ZONA", "SECAO",\n            "REGISTRO", "IDENTIDADE", "NASCIMENTO", "EMISSAO",\n            "VALIDADE", "CNS", "CTPS"\n        ]) and not rotulo:\n            pontos -= 45\n\n        if len(set(numero)) <= 3:\n            pontos -= 30\n\n        candidatos.append((pontos, numero))\n\n    for i, bloco in enumerate(blocos):\n        valor = texto(bloco)\n        adicionar(somente_numeros(valor), valor, i)\n\n    # Telefones manuscritos às vezes são quebrados em 2 ou 3 blocos.\n    for i in range(len(blocos)):\n        partes = []\n        for j in range(i, min(i + 3, len(blocos))):\n            bruto = texto(blocos[j])\n            nums = somente_numeros(bruto)\n            if not nums or len(nums) > 7:\n                break\n\n            if j > i:\n                try:\n                    a = blocos[j - 1]\n                    b = blocos[j]\n                    if a.get("pagina") != b.get("pagina"):\n                        break\n                    dx = abs(float(b["x_relativo"]) - float(a["x_relativo"]))\n                    dy = abs(float(b["y_relativo"]) - float(a["y_relativo"]))\n                    if dx > 0.18 or dy > 0.08:\n                        break\n                except Exception:\n                    pass\n\n            partes.append(nums)\n            combinado = "".join(partes)\n            if len(combinado) in (8, 9, 10, 11):\n                valor_combinado = " ".join(texto(blocos[k]) for k in range(i, j + 1))\n                adicionar(combinado, valor_combinado, i, bonus=20)\n\n    if not candidatos:\n        return ""\n\n    candidatos.sort(key=lambda item: item[0], reverse=True)\n    pontos, numero = candidatos[0]\n\n    if pontos < 60:\n        return ""\n\n    return formatar_telefone(numero)\n\n\n# ============================================================\n# ZONA / SEÇÃO\n# ============================================================\n\ndef extrair_zona_secao(blocos, indice_titulo):\n    """\n    Extrai ZONA e SEÇÃO sem depender de layout fixo.\n\n    Estratégia:\n    1) procura os rótulos ZONA e SEÇÃO em toda a página;\n    2) aceita o número imediatamente antes OU depois do rótulo;\n    3) dá preferência aos candidatos próximos ao TÍTULO ELEITORAL;\n    4) evita confundir data, CPF, título e números longos.\n    """\n\n    def numero_curto(indice, max_digitos):\n        if indice < 0 or indice >= len(blocos):\n            return None\n\n        valor = somente_numeros(texto(blocos[indice]))\n\n        if not valor:\n            return None\n\n        if not (1 <= len(valor) <= max_digitos):\n            return None\n\n        return valor\n\n    def distancia_titulo(indice):\n        if indice_titulo is None:\n            return 999\n        return abs(indice - indice_titulo)\n\n    zona_candidatos = []\n    secao_candidatos = []\n\n    # --------------------------------------------------------\n    # 1) RÓTULOS EXPLÍCITOS\n    # --------------------------------------------------------\n\n    for indice, bloco in enumerate(blocos):\n        normal = sem_acentos(texto(bloco))\n        comp = compacto(texto(bloco))\n\n        eh_zona = (\n            normal == "ZONA"\n            or "ZONA" in normal\n            or comp == "ZONA"\n        )\n\n        eh_secao = (\n            normal == "SECAO"\n            or "SECAO" in normal\n            or comp == "SECAO"\n        )\n\n        if eh_zona:\n            # OCR pode devolver o valor antes ou depois do rótulo.\n            for deslocamento in [-1, 1, -2, 2, -3, 3, -4, 4]:\n                j = indice + deslocamento\n                numero = numero_curto(j, 3)\n\n                if numero is None:\n                    continue\n\n                pontos = 100\n                pontos -= abs(deslocamento) * 8\n                pontos -= distancia_titulo(j) * 2\n                pontos += confianca(blocos[j]) * 10\n\n                zona_candidatos.append(\n                    (pontos, j, numero)\n                )\n\n        if eh_secao:\n            for deslocamento in [-1, 1, -2, 2, -3, 3, -4, 4]:\n                j = indice + deslocamento\n                numero = numero_curto(j, 4)\n\n                if numero is None:\n                    continue\n\n                pontos = 100\n                pontos -= abs(deslocamento) * 8\n                pontos -= distancia_titulo(j) * 2\n                pontos += confianca(blocos[j]) * 10\n\n                secao_candidatos.append(\n                    (pontos, j, numero)\n                )\n\n    # --------------------------------------------------------\n    # 2) FALLBACK: REGIÃO DO TÍTULO\n    # --------------------------------------------------------\n    # Em vários títulos o OCR reconhece:\n    #\n    # TITULO ...\n    # nascimento\n    # número do título\n    # zona\n    # seção\n    #\n    # mas pode falhar justamente nos rótulos.\n    # Por isso analisamos números curtos perto do título.\n    # --------------------------------------------------------\n\n    if indice_titulo is not None:\n\n        inicio = max(0, indice_titulo - 6)\n        fim = min(len(blocos), indice_titulo + 10)\n\n        curtos = []\n\n        for j in range(inicio, fim):\n            if j == indice_titulo:\n                continue\n\n            valor_original = texto(blocos[j])\n            numero = somente_numeros(valor_original)\n\n            if not numero:\n                continue\n\n            # Ignora datas e números longos.\n            if "/" in valor_original:\n                continue\n\n            if 1 <= len(numero) <= 4:\n                curtos.append(\n                    (\n                        j,\n                        numero,\n                        abs(j - indice_titulo),\n                        confianca(blocos[j])\n                    )\n                )\n\n        # Zona normalmente tem até 3 dígitos.\n        if not zona_candidatos:\n            for j, numero, distancia, conf in curtos:\n                if len(numero) <= 3:\n                    pontos = 40\n                    pontos -= distancia * 3\n                    pontos += conf * 10\n\n                    zona_candidatos.append(\n                        (pontos, j, numero)\n                    )\n\n        # Seção normalmente tem até 4 dígitos.\n        if not secao_candidatos:\n            for j, numero, distancia, conf in curtos:\n                if len(numero) <= 4:\n                    pontos = 35\n                    pontos -= distancia * 3\n                    pontos += conf * 10\n\n                    secao_candidatos.append(\n                        (pontos, j, numero)\n                    )\n\n    # --------------------------------------------------------\n    # ESCOLHER MELHORES\n    # --------------------------------------------------------\n\n    zona = ""\n    secao = ""\n    indice_zona = None\n\n    if zona_candidatos:\n        zona_candidatos.sort(\n            key=lambda item: item[0],\n            reverse=True\n        )\n\n        _, indice_zona, zona = zona_candidatos[0]\n\n    if secao_candidatos:\n        # Evita usar exatamente o mesmo bloco escolhido como zona,\n        # quando houver outro candidato plausível para seção.\n        diferentes = [\n            item\n            for item in secao_candidatos\n            if item[1] != indice_zona\n        ]\n\n        lista = (\n            diferentes\n            if diferentes\n            else secao_candidatos\n        )\n\n        lista.sort(\n            key=lambda item: item[0],\n            reverse=True\n        )\n\n        _, _, secao = lista[0]\n\n    # Mantém zeros à esquerda para a planilha.\n    if zona:\n        zona = zona.zfill(3)\n\n    if secao:\n        secao = secao.zfill(4)\n\n    return zona, secao\n\n\n# ============================================================\n# RG\n# ============================================================\n\ndef extrair_rg(blocos, cpf, titulo):\n    proibidos = {\n        somente_numeros(cpf),\n        somente_numeros(titulo),\n        ""\n    }\n\n    candidatos = []\n\n    for indice, bloco in enumerate(blocos):\n        valor = texto(bloco)\n        numero = somente_numeros(valor)\n\n        if not (6 <= len(numero) <= 10):\n            continue\n\n        if numero in proibidos:\n            continue\n\n        if len(numero) == 8:\n            try:\n                datetime.strptime(numero, "%d%m%Y")\n                continue\n            except ValueError:\n                pass\n\n        pontos = confianca(bloco) * 15\n\n        inicio = max(0, indice - 8)\n        fim = min(len(blocos), indice + 9)\n\n        contexto = " ".join(\n            sem_acentos(texto(b))\n            for b in blocos[inicio:fim]\n        )\n\n        if "DOC IDENTIDADE" in contexto:\n            pontos += 120\n\n        if "REGISTRO GERAL" in contexto:\n            pontos += 110\n\n        if re.search(r"\x08RG\x08", contexto):\n            pontos += 100\n\n        if "IDENTIDADE" in contexto:\n            pontos += 45\n\n        if any(\n            termo in contexto\n            for termo in [\n                "SSP",\n                "SCJDS",\n                "ORGAO EXPEDIDOR",\n                "ORG EXPEDIDOR",\n                "EXPEDIDOR"\n            ]\n        ):\n            pontos += 45\n\n        if 7 <= len(numero) <= 9:\n            pontos += 25\n\n        normal_valor = sem_acentos(valor)\n\n        # Ex.: "31213766 SCJDS AL"\n        if "SSP" in normal_valor or "SCJDS" in normal_valor:\n            pontos += 80\n\n        if any(\n            termo in contexto\n            for termo in [\n                "CEP",\n                "TELEFONE",\n                "CELULAR",\n                "FONE",\n                "MATRICULA",\n                "HIDROMETRO",\n                "CONSUMO",\n                "FATURA"\n            ]\n        ):\n            pontos -= 50\n\n        candidatos.append(\n            (pontos, numero)\n        )\n\n    if not candidatos:\n        return ""\n\n    candidatos.sort(\n        key=lambda item: item[0],\n        reverse=True\n    )\n\n    if candidatos[0][0] < 55:\n        return ""\n\n    return candidatos[0][1]\n\n\n# ============================================================\n# NOME DA MÃE\n# ============================================================\n\ndef _nome_filiacao_valido(valor, nome_principal):\n    valor = limpar_texto(valor)\n    if not parece_nome(valor):\n        return False\n\n    normal = sem_acentos(valor)\n    if nome_principal and normal == sem_acentos(nome_principal):\n        return False\n\n    proibidos = [\n        "RESPONSAVEL", "CLIENTE", "CPF", "CNPJ", "ENDERECO",\n        "COMPANHIA", "SANEAMENTO", "CASAL", "FATURA", "CONSUMO",\n        "VENCIMENTO", "MATRICULA", "HIDROMETRO", "ASSINATURA",\n        "PORTADOR", "NACIONALIDADE", "VALIDADE", "NASCIMENTO",\n        "IDENTIDADE", "REGISTRO", "ELEITORAL", "SECRETARIA",\n        "REPUBLICA", "BRASILEIRO", "ORGAO", "EXPEDIDOR"\n    ]\n    if any(termo in normal for termo in proibidos):\n        return False\n\n    palavras = re.findall(r"[A-ZÀ-Ú]+", normal)\n    return len(palavras) >= 2\n\n\ndef extrair_nome_mae(blocos, nome):\n    """Extrai mãe por MÃE/MOTHER ou FILIAÇÃO/FILIATION, sem layout fixo."""\n    def rmae(v):\n        n,c=sem_acentos(v),compacto(v)\n        return n in {"MAE","MOTHER","NOME DA MAE","MOTHERS NAME"} or "NOMEDAMAE" in c or "MOTHERSNAME" in c\n    def rfil(v):\n        n,c=sem_acentos(v),compacto(v)\n        return "FILIACAO" in n or "FILIATION" in n or "PARENTAGE" in n or c in {"FILIACAO","FILIATION","PARENTS","PARENTAGE"}\n    for i,b in enumerate(blocos):\n        if not rmae(texto(b)): continue\n        for j in range(i+1,min(i+12,len(blocos))):\n            v=texto(blocos[j])\n            if _nome_filiacao_valido(v,nome) and not re.search(r"[/\\-]\\s*[A-Z]{2}\\s*$",v.upper()): return v.upper()\n    ctx=" ".join(sem_acentos(texto(b)) for b in blocos)\n    eleitoral=any(t in ctx for t in ["JUSTICA ELEITORAL","TITULO ELEITORAL","ELEITOR","E-TITULO"])\n    for i,b in enumerate(blocos):\n        if not rfil(texto(b)): continue\n        nomes=[]\n        for j in range(i+1,min(i+22,len(blocos))):\n            v=texto(blocos[j]); n=sem_acentos(v)\n            if nomes and any(t in n for t in ["ASSINATURA","CPF/CNPJ","ENDERECO","OBSERVACOES","NASCIMENTO","VALIDADE"]): break\n            if _nome_filiacao_valido(v,nome) and not re.search(r"[/\\-]\\s*[A-Z]{2}\\s*$",v.upper()):\n                vu=v.upper()\n                if sem_acentos(vu) not in [sem_acentos(x) for x in nomes]: nomes.append(vu)\n            if len(nomes)>=2: break\n        if nomes: return nomes[0] if eleitoral or len(nomes)==1 else nomes[1]\n    return ""\n\n\ndef extrair_endereco(blocos):\n    tipos = [\n        "RUA ",\n        "AVENIDA ",\n        "AV ",\n        "TRAVESSA ",\n        "TV ",\n        "RODOVIA ",\n        "ESTRADA ",\n        "SITIO ",\n        "POVOADO ",\n        "LOTEAMENTO ",\n        "RESIDENCIAL ",\n        "CONJUNTO ",\n        "PRACA "\n    ]\n\n    for bloco in blocos:\n        valor = texto(bloco)\n        normal = sem_acentos(valor)\n\n        if any(\n            normal.startswith(tipo)\n            for tipo in tipos\n        ):\n            return valor.upper()\n\n    return ""\n\n\n# ============================================================\n# CIDADE\n# ============================================================\n\ndef extrair_cidade(blocos):\n    for bloco in blocos:\n        valor = texto(bloco)\n        normal = sem_acentos(valor)\n\n        # Exemplos:\n        # ARAPIRACA/AL\n        # ARAPIRACA-AL\n        match = re.search(\n            r"\\b([A-ZÀ-Ú][A-ZÀ-Ú\\s]{2,})"\n            r"[\\-/]"\n            r"([A-Z]{2})\\b",\n            valor.upper()\n        )\n\n        if match:\n            cidade = limpar_texto(\n                match.group(1)\n            )\n\n            if cidade:\n                return cidade.upper()\n\n        # OCR pode colar:\n        # ARAPIRACAVAL\n        if normal.endswith("AL") and len(normal) > 4:\n            candidato = re.sub(\n                r"[^A-Z]",\n                "",\n                normal\n            )\n\n            if candidato.endswith("AL"):\n                candidato = candidato[:-2]\n\n                # Evita palavras aleatórias.\n                if len(candidato) >= 4:\n                    return candidato\n\n    return ""\n\n\n# ============================================================\n# EXTRATOR PRINCIPAL\n# ============================================================\n\n\n# ============================================================\n# LEITURA POR RÓTULOS EXPLÍCITOS\n# ============================================================\n\ndef _distancia(a, b):\n    try:\n        ax, ay = float(a["x_relativo"]), float(a["y_relativo"])\n        bx, by = float(b["x_relativo"]), float(b["y_relativo"])\n        return ((ax-bx)**2 + (ay-by)**2) ** 0.5\n    except Exception:\n        return 999.0\n\n\ndef _eh_rotulo(valor):\n    n = sem_acentos(valor)\n    c = compacto(valor)\n    termos = [\n        "NOME DO ELEITOR", "NOMEDOELEITOR", "DATA DE NASCIMENTO",\n        "DATADENASCIMENTO", "INSCRICAO", "ZONA", "SECAO", "MUNICIPIO",\n        "FILIACAO", "CODIGO DE VALIDACAO", "CODIGODEVALIDACAO",\n        "DATA DE EMISSAO", "JUSTICA ELEITORAL", "REPUBLICA FEDERATIVA",\n        "TITULO ELEITORAL"\n    ]\n    return any(t in n or t in c for t in termos)\n\n\ndef _nome_forte(valor):\n    valor = limpar_texto(valor)\n    if re.search(r"[/\\-]\\s*[A-Z]{2}\\s*$", valor.upper()):\n        return False\n    if not parece_nome(valor) or _eh_rotulo(valor):\n        return False\n    n = sem_acentos(valor)\n    proibidos = [\n        "CODIGO", "VALIDACAO", "JUSTICA", "ELEITORAL", "REPUBLICA",\n        "FEDERATIVA", "BRASIL", "ORIENTACOES", "TRIBUNAL", "INTERNET",\n        "MUNICIPIO", "BIOMETRIA", "ELEITOR", "ELEITORA", "TITULO"\n    ]\n    return not any(p in n for p in proibidos)\n\n\ndef _perto(blocos, i, limite):\n    r = blocos[i]\n    itens = []\n    for j, b in enumerate(blocos):\n        if j == i or b.get("pagina") != r.get("pagina"):\n            continue\n        d = _distancia(r, b)\n        if d <= limite:\n            itens.append((d, j, b))\n    return sorted(itens, key=lambda x: x[0])\n\n\ndef extrair_nome_rotulado(blocos):\n    rotulos={"NOME","NAME","FULLNAME","NOMECOMPLETO","NOMEDOELEITOR","NOMEDAELEITORA"}\n    for i,b in enumerate(blocos):\n        c=compacto(texto(b))\n        if c not in rotulos and not any(r in c for r in ("NOMEDOELEITOR","NOMEDAELEITORA")): continue\n        candidatos=[]\n        for d,_,cand in _perto(blocos,i,0.22):\n            v=limpar_texto(texto(cand))\n            if _nome_forte(v): candidatos.append((100-d*200+confianca(cand)*10,v.upper()))\n        if candidatos: return max(candidatos,key=lambda x:x[0])[1]\n    return ""\n\n\ndef extrair_cidade_rotulada(blocos):\n    for i, b in enumerate(blocos):\n        n = sem_acentos(texto(b))\n        if "MUNICIPIO" not in n:\n            continue\n        candidatos = []\n        for d, _, cand in _perto(blocos, i, 0.15):\n            v = limpar_texto(texto(cand)).upper()\n            vn = sem_acentos(v)\n            if _eh_rotulo(v) or any(x in vn for x in ["CODIGO","VALIDACAO","JUSTICA","ELEITORAL"]):\n                continue\n            m = re.match(r"^\\s*([A-ZÀ-Ú][A-ZÀ-Ú\\s.\'-]{2,}?)(?:\\s*[/\\-]\\s*[A-Z]{2})?\\s*$", v)\n            if m:\n                cidade = limpar_texto(m.group(1)).strip(" -/")\n                if len(cidade) >= 3:\n                    candidatos.append((100-d*200, cidade))\n        if candidatos:\n            return max(candidatos)[1]\n    return ""\n\n\ndef extrair_zona_secao_rotuladas(blocos):\n    saida = {"ZONA": "", "SEÇÃO": ""}\n    for chave, termo in [("ZONA","ZONA"), ("SEÇÃO","SECAO")]:\n        melhores = []\n        for i, b in enumerate(blocos):\n            if termo not in sem_acentos(texto(b)):\n                continue\n            for d, _, cand in _perto(blocos, i, 0.09):\n                bruto = limpar_texto(texto(cand))\n                num = somente_numeros(bruto)\n                if not num or len(num) > 4:\n                    continue\n                # bloco deve ser essencialmente numérico\n                if len(num) < max(1, len(bruto.replace(" ","")) - 1):\n                    continue\n                pontos = 100-d*300\n                try:\n                    dx = abs(float(cand["x_relativo"])-float(b["x_relativo"]))\n                    if dx < 0.055:\n                        pontos += 35\n                except Exception:\n                    pass\n                melhores.append((pontos, num))\n        if melhores:\n            valor = max(melhores)[1]\n            saida[chave] = valor.zfill(3 if chave=="ZONA" else 4)\n    return saida["ZONA"], saida["SEÇÃO"]\n\n\ndef extrair_mae_filiacao_rotulada(blocos, nome_principal):\n    contexto=" ".join(sem_acentos(texto(b)) for b in blocos)\n    eleitoral=any(t in contexto for t in ["JUSTICA ELEITORAL","TITULO ELEITORAL","ELEITOR","E-TITULO"])\n    for i,b in enumerate(blocos):\n        c=compacto(texto(b))\n        if not any(t in c for t in ("FILIACAO","FILIATION","PARENTAGE","PARENTS")): continue\n        candidatos=[]\n        for d,j,cand in _perto(blocos,i,0.24):\n            v=limpar_texto(texto(cand))\n            if not _nome_filiacao_valido(v,nome_principal): continue\n            if re.search(r"[/\\-]\\s*[A-Z]{2}\\s*$",v.upper()): continue\n            try: y=float(cand.get("y_relativo",9)); x=float(cand.get("x_relativo",9))\n            except Exception: y,x=9,9\n            candidatos.append((y,x,d,j,v.upper()))\n        if candidatos:\n            candidatos.sort(key=lambda z:(z[0],z[1],z[3]))\n            return candidatos[0][4] if eleitoral or len(candidatos)==1 else candidatos[1][4]\n    return ""\n\n\ndef extrair_dados(blocos, recuperados=None):\n\n    # Segurança: garante que estamos usando a versão correta.\n    if blocos and not isinstance(blocos[0], dict):\n        raise TypeError(\n            "O extrator V2 esperava blocos do RapidOCR, "\n            "mas recebeu textos simples."\n        )\n\n    nome = extrair_nome(blocos)\n\n    cpf = extrair_cpf(blocos)\n\n    nascimento = extrair_nascimento(\n        blocos\n    )\n\n    titulo, indice_titulo = extrair_titulo(\n        blocos\n    )\n\n    zona, secao = extrair_zona_secao(\n        blocos,\n        indice_titulo\n    )\n\n    rg = extrair_rg(\n        blocos,\n        cpf,\n        titulo\n    )\n\n    nome_mae = extrair_nome_mae(\n        blocos,\n        nome\n    )\n\n    telefone = extrair_telefone(\n        blocos,\n        cpf,\n        titulo\n    )\n\n    endereco = extrair_endereco(\n        blocos\n    )\n\n    cidade = extrair_cidade(\n        blocos\n    )\n\n    # Rótulos explícitos têm prioridade sobre heurísticas genéricas.\n    nome_rotulo = extrair_nome_rotulado(blocos)\n    if nome_rotulo:\n        nome = nome_rotulo\n\n    cidade_rotulo = extrair_cidade_rotulada(blocos)\n    if cidade_rotulo:\n        cidade = cidade_rotulo\n\n    zona_rotulo, secao_rotulo = extrair_zona_secao_rotuladas(blocos)\n    if zona_rotulo:\n        zona = zona_rotulo\n    if secao_rotulo:\n        secao = secao_rotulo\n\n    mae_rotulo = extrair_mae_filiacao_rotulada(blocos, nome)\n    if mae_rotulo:\n        nome_mae = mae_rotulo\n\n    recuperados = recuperados or {}\n\n    mae_recuperada = limpar_texto(\n        recuperados.get("NOME DA MÃE", "")\n    )\n    telefone_recuperado = limpar_texto(\n        recuperados.get("TELEFONE", "")\n    )\n\n    if mae_recuperada:\n        nome_mae = mae_recuperada.upper()\n\n    if telefone_recuperado:\n        telefone = telefone_recuperado\n\n    return {\n        "NOME": nome,\n        "CPF": cpf,\n        "RG": rg,\n        "DATA DE NASCIMENTO": nascimento,\n        "NOME DA MÃE": nome_mae,\n\n        "ENDEREÇO": endereco,\n        "Nº": "",\n        "BAIRRO": "",\n        "CIDADE": cidade,\n\n        "TITULO": titulo,\n        "ZONA": zona,\n        "SEÇÃO": secao,\n\n        "TELEFONE": telefone\n    }\n\n\n# ============================================================\n# MOSTRAR RESULTADO\n# ============================================================\n\ndef mostrar_dados(dados):\n\n    print()\n    print("=" * 70)\n    print("DADOS EXTRAÍDOS")\n    print("=" * 70)\n\n    ordem = [\n        "NOME",\n        "CPF",\n        "RG",\n        "DATA DE NASCIMENTO",\n        "NOME DA MÃE",\n        "ENDEREÇO",\n        "Nº",\n        "BAIRRO",\n        "CIDADE",\n        "TITULO",\n        "ZONA",\n        "SEÇÃO",\n        "TELEFONE"\n    ]\n\n    for campo in ordem:\n        valor = dados.get(campo, "")\n\n        if not valor:\n            valor = "NÃO ENCONTRADO"\n\n        print(\n            f"{campo:<20}: {valor}"\n        )\n\n    print("=" * 70)', _MOTOR_VSCODE)

# ============================================================
# 23. EXTRAIR DADOS OCR
# ============================================================

def extrair_dados_ocr(
    texto,
    itens
):
    # Aqui roda EXATAMENTE a função extrair_dados do VSCode.
    dados = _MOTOR_VSCODE["extrair_dados"](itens)

    # Apenas converte os nomes das chaves para o formato já usado
    # pelo Streamlit. Nenhuma interpretação adicional é feita aqui.
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
