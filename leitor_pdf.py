import io
import gc

import fitz
from PIL import Image


# ============================================================
# CONFIGURAÇÕES
# ============================================================

MIN_CARACTERES_TEXTO_DIGITAL = 80

ZOOM_PADRAO_OCR = 250 / 72


# ============================================================
# ABRIR PDF
# ============================================================

def abrir_pdf(pdf_bytes):
    """
    Abre um PDF a partir dos bytes recebidos.

    O documento retornado deve ser fechado
    pela função que o utilizar.
    """

    return fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )


# ============================================================
# EXTRAIR TEXTO NATIVO
# ============================================================

def extrair_texto_pdf_digital(
    pdf_bytes
):
    """
    Extrai o texto nativo de todas as páginas.

    Não executa OCR.

    Retorna:
        texto_completo
        paginas_texto
    """

    documento = abrir_pdf(
        pdf_bytes
    )

    paginas_texto = []

    try:

        for numero_pagina in range(
            len(documento)
        ):

            pagina = documento[
                numero_pagina
            ]

            texto = pagina.get_text(
                "text"
            )

            texto = str(
                texto or ""
            ).strip()

            paginas_texto.append(
                texto
            )

    finally:

        documento.close()

    texto_completo = "\n\n".join(
        texto
        for texto in paginas_texto
        if texto
    ).strip()

    return (
        texto_completo,
        paginas_texto
    )


# ============================================================
# MEDIR TEXTO ÚTIL
# ============================================================

def contar_caracteres_uteis(
    texto
):
    """
    Conta somente letras e números.

    Evita considerar símbolos soltos de um
    PDF escaneado como texto digital válido.
    """

    return sum(
        1
        for caractere in str(
            texto or ""
        )
        if caractere.isalnum()
    )


# ============================================================
# VERIFICAR SE PDF É DIGITAL
# ============================================================

def pdf_tem_texto_util(
    pdf_bytes,
    minimo_caracteres=MIN_CARACTERES_TEXTO_DIGITAL
):
    """
    Retorna True somente quando o PDF possui
    texto nativo suficiente para ser tratado
    como PDF digital.
    """

    texto, _ = (
        extrair_texto_pdf_digital(
            pdf_bytes
        )
    )

    quantidade = (
        contar_caracteres_uteis(
            texto
        )
    )

    return (
        quantidade
        >= minimo_caracteres
    )


# ============================================================
# ANALISAR PÁGINAS INDIVIDUALMENTE
# ============================================================

def analisar_paginas_pdf(
    pdf_bytes,
    minimo_caracteres=MIN_CARACTERES_TEXTO_DIGITAL
):
    """
    Analisa cada página separadamente.

    Isso é importante porque um mesmo PDF pode ter:

        página 1 -> texto digital
        página 2 -> documento escaneado
        página 3 -> texto digital

    Portanto não classificamos obrigatoriamente
    o PDF inteiro de uma única forma.
    """

    documento = abrir_pdf(
        pdf_bytes
    )

    paginas = []

    try:

        for numero_pagina in range(
            len(documento)
        ):

            pagina = documento[
                numero_pagina
            ]

            texto = pagina.get_text(
                "text"
            )

            texto = str(
                texto or ""
            ).strip()

            quantidade = (
                contar_caracteres_uteis(
                    texto
                )
            )

            tem_texto = (
                quantidade
                >= minimo_caracteres
            )

            paginas.append(
                {
                    "pagina":
                        numero_pagina + 1,

                    "texto":
                        texto,

                    "caracteres_uteis":
                        quantidade,

                    "tem_texto_digital":
                        tem_texto,

                    "tipo":
                        (
                            "PDF_DIGITAL"
                            if tem_texto
                            else "PDF_ESCANEADO"
                        )
                }
            )

    finally:

        documento.close()

    return paginas


# ============================================================
# CONVERTER UMA PÁGINA EM IMAGEM
# ============================================================

def converter_pagina_em_imagem(
    pagina,
    zoom=ZOOM_PADRAO_OCR
):
    """
    Converte uma página PyMuPDF para imagem PIL.

    Não executa OCR.
    """

    matriz = fitz.Matrix(
        zoom,
        zoom
    )

    pixmap = pagina.get_pixmap(
        matrix=matriz,
        alpha=False
    )

    imagem_bytes = (
        pixmap.tobytes(
            "png"
        )
    )

    imagem = Image.open(
        io.BytesIO(
            imagem_bytes
        )
    ).convert(
        "RGB"
    )

    resultado = imagem.copy()

    imagem.close()

    del imagem
    del imagem_bytes
    del pixmap

    gc.collect()

    return resultado


# ============================================================
# CONVERTER TODAS AS PÁGINAS
# ============================================================

def converter_pdf_em_imagens(
    pdf_bytes,
    zoom=ZOOM_PADRAO_OCR
):
    """
    Converte todas as páginas do PDF
    em imagens.

    Retorna:

    [
        {
            "pagina": 1,
            "imagem": PIL.Image
        },
        ...
    ]
    """

    documento = abrir_pdf(
        pdf_bytes
    )

    paginas = []

    try:

        for numero_pagina in range(
            len(documento)
        ):

            pagina = documento[
                numero_pagina
            ]

            imagem = (
                converter_pagina_em_imagem(
                    pagina,
                    zoom=zoom
                )
            )

            paginas.append(
                {
                    "pagina":
                        numero_pagina + 1,

                    "imagem":
                        imagem
                }
            )

    finally:

        documento.close()

    return paginas


# ============================================================
# CONVERTER SOMENTE PÁGINAS ESCANEADAS
# ============================================================

def converter_paginas_escaneadas(
    pdf_bytes,
    zoom=ZOOM_PADRAO_OCR,
    minimo_caracteres=MIN_CARACTERES_TEXTO_DIGITAL
):
    """
    Converte para imagem SOMENTE as páginas
    que não possuem texto digital suficiente.

    Isso evita OCR desnecessário em páginas
    que já possuem texto nativo.
    """

    documento = abrir_pdf(
        pdf_bytes
    )

    paginas = []

    try:

        for numero_pagina in range(
            len(documento)
        ):

            pagina = documento[
                numero_pagina
            ]

            texto = pagina.get_text(
                "text"
            )

            texto = str(
                texto or ""
            ).strip()

            quantidade = (
                contar_caracteres_uteis(
                    texto
                )
            )

            if (
                quantidade
                >= minimo_caracteres
            ):
                continue

            imagem = (
                converter_pagina_em_imagem(
                    pagina,
                    zoom=zoom
                )
            )

            paginas.append(
                {
                    "pagina":
                        numero_pagina + 1,

                    "imagem":
                        imagem
                }
            )

    finally:

        documento.close()

    return paginas


# ============================================================
# ANÁLISE COMPLETA DO PDF
# ============================================================

def analisar_pdf(
    pdf_bytes,
    minimo_caracteres=MIN_CARACTERES_TEXTO_DIGITAL
):
    """
    Faz a classificação estrutural do PDF.

    Ainda NÃO executa OCR.

    O retorno informa:

    - quantidade de páginas;
    - quais páginas são digitais;
    - quais precisam de OCR;
    - texto digital encontrado;
    - se o PDF é digital, escaneado ou misto.
    """

    paginas = analisar_paginas_pdf(
        pdf_bytes,
        minimo_caracteres=minimo_caracteres
    )

    paginas_digitais = [
        pagina
        for pagina in paginas
        if pagina[
            "tem_texto_digital"
        ]
    ]

    paginas_escaneadas = [
        pagina
        for pagina in paginas
        if not pagina[
            "tem_texto_digital"
        ]
    ]

    if (
        paginas_digitais
        and paginas_escaneadas
    ):
        tipo = "PDF_MISTO"

    elif paginas_digitais:
        tipo = "PDF_DIGITAL"

    else:
        tipo = "PDF_ESCANEADO"

    texto_completo = "\n\n".join(
        pagina["texto"]
        for pagina in paginas_digitais
        if pagina["texto"]
    ).strip()

    return {
        "tipo":
            tipo,

        "total_paginas":
            len(paginas),

        "paginas":
            paginas,

        "paginas_digitais":
            [
                pagina["pagina"]
                for pagina
                in paginas_digitais
            ],

        "paginas_escaneadas":
            [
                pagina["pagina"]
                for pagina
                in paginas_escaneadas
            ],

        "tem_texto_digital":
            bool(
                paginas_digitais
            ),

        "precisa_ocr":
            bool(
                paginas_escaneadas
            ),

        "texto":
            texto_completo,

        "paginas_texto":
            [
                pagina["texto"]
                for pagina
                in paginas
            ]
    }
