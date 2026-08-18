import io
import gc

import fitz
from PIL import Image


def extrair_texto_pdf_digital(pdf_bytes):
    """
    Tenta extrair texto nativo de um PDF.

    Retorna:
        texto_completo
        paginas_texto
    """

    documento = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
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


def pdf_tem_texto_util(pdf_bytes):
    """
    Verifica se o PDF possui texto digital
    suficiente para dispensar OCR.

    Não considera algumas poucas letras perdidas
    como um PDF realmente digital.
    """

    texto, paginas = (
        extrair_texto_pdf_digital(
            pdf_bytes
        )
    )

    caracteres = "".join(
        caractere
        for caractere in texto
        if caractere.isalnum()
    )

    return len(caracteres) >= 80


def converter_pdf_em_imagens(
    pdf_bytes,
    zoom=2.5
):
    """
    Converte todas as páginas de um PDF
    em imagens PIL.

    Usado quando o PDF é escaneado
    ou quando precisarmos aplicar OCR.
    """

    documento = fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    )

    paginas = []

    try:

        matriz = fitz.Matrix(
            zoom,
            zoom
        )

        for numero_pagina in range(
            len(documento)
        ):

            pagina = documento[
                numero_pagina
            ]

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

            paginas.append(
                {
                    "pagina":
                        numero_pagina + 1,

                    "imagem":
                        imagem.copy()
                }
            )

            imagem.close()

            del imagem
            del imagem_bytes
            del pixmap

            gc.collect()

    finally:

        documento.close()

    return paginas


def analisar_pdf(pdf_bytes):
    """
    Faz somente a classificação inicial do PDF.

    Retorna um dicionário informando se
    o arquivo possui texto digital utilizável.

    Ainda NÃO executa OCR.
    """

    texto, paginas_texto = (
        extrair_texto_pdf_digital(
            pdf_bytes
        )
    )

    caracteres = "".join(
        caractere
        for caractere in texto
        if caractere.isalnum()
    )

    tem_texto = (
        len(caracteres) >= 80
    )

    return {
        "tipo":
            (
                "PDF_DIGITAL"
                if tem_texto
                else "PDF_ESCANEADO"
            ),

        "tem_texto_digital":
            tem_texto,

        "texto":
            texto,

        "paginas_texto":
            paginas_texto
    }
