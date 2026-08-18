import io
import gc

from PIL import Image

from leitor_pdf import (
    analisar_pdf,
    converter_pdf_em_imagens
)

from leitor_imagem import (
    preparar_para_ocr
)

from extrator_documentos import (
    analisar_documentos
)


# ============================================================
# IDENTIFICAR FORMATO DO ARQUIVO
# ============================================================

def identificar_formato(nome_arquivo):
    nome = str(
        nome_arquivo or ""
    ).lower().strip()

    if nome.endswith(".pdf"):
        return "PDF"

    if nome.endswith(
        (
            ".jpg",
            ".jpeg",
            ".png"
        )
    ):
        return "IMAGEM"

    return "DESCONHECIDO"


# ============================================================
# ABRIR IMAGEM
# ============================================================

def abrir_imagem(arquivo_bytes):
    imagem = Image.open(
        io.BytesIO(
            arquivo_bytes
        )
    )

    return imagem.convert(
        "RGB"
    )


# ============================================================
# PREPARAR PDF
# ============================================================

def preparar_pdf(arquivo_bytes):
    """
    Analisa o PDF.

    Se possuir texto digital utilizável:
        retorna o texto diretamente.

    Se for escaneado:
        converte todas as páginas para imagens.

    Ainda NÃO executa OCR.
    """

    analise = analisar_pdf(
        arquivo_bytes
    )

    if analise[
        "tem_texto_digital"
    ]:

        return {
            "formato":
                "PDF",

            "tipo":
                "PDF_DIGITAL",

            "texto":
                analise["texto"],

            "paginas_texto":
                analise[
                    "paginas_texto"
                ],

            "paginas_imagem":
                [],

            "documentos":
                analisar_documentos(
                    analise["texto"]
                )
        }

    paginas = (
        converter_pdf_em_imagens(
            arquivo_bytes
        )
    )

    return {
        "formato":
            "PDF",

        "tipo":
            "PDF_ESCANEADO",

        "texto":
            "",

        "paginas_texto":
            [],

        "paginas_imagem":
            paginas,

        "documentos":
            None
    }


# ============================================================
# PREPARAR IMAGEM
# ============================================================

def preparar_arquivo_imagem(
    arquivo_bytes
):
    """
    Abre JPG/JPEG/PNG e prepara para OCR.

    Ainda NÃO executa OCR.
    """

    imagem_original = abrir_imagem(
        arquivo_bytes
    )

    try:

        imagem_ocr = (
            preparar_para_ocr(
                imagem_original
            )
        )

        return {
            "formato":
                "IMAGEM",

            "tipo":
                "IMAGEM",

            "texto":
                "",

            "paginas_texto":
                [],

            "paginas_imagem":
                [
                    {
                        "pagina": 1,
                        "imagem":
                            imagem_ocr.copy()
                    }
                ],

            "documentos":
                None
        }

    finally:

        imagem_original.close()

        del imagem_original

        gc.collect()


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def preparar_documento(
    nome_arquivo,
    arquivo_bytes
):
    """
    Porta de entrada dos leitores.

    Decide automaticamente qual módulo usar
    de acordo com o arquivo recebido.
    """

    formato = identificar_formato(
        nome_arquivo
    )

    if formato == "PDF":

        return preparar_pdf(
            arquivo_bytes
        )

    if formato == "IMAGEM":

        return preparar_arquivo_imagem(
            arquivo_bytes
        )

    raise ValueError(
        "Formato de arquivo não suportado: "
        + str(nome_arquivo)
    )
