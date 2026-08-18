import io
import gc

from PIL import (
    Image,
    ImageEnhance,
    ImageFilter,
    ImageOps
)


# ============================================================
# CONFIGURAÇÕES
# ============================================================

LARGURA_MINIMA = 2000
LARGURA_MAXIMA = 3000


# ============================================================
# ABRIR IMAGEM
# ============================================================

def abrir_imagem(arquivo_bytes):
    """
    Abre JPG, JPEG ou PNG a partir dos bytes.

    Corrige também a orientação registrada
    nos metadados EXIF da imagem.
    """

    imagem = Image.open(
        io.BytesIO(
            arquivo_bytes
        )
    )

    imagem = ImageOps.exif_transpose(
        imagem
    )

    return imagem.convert(
        "RGB"
    )


# ============================================================
# REDIMENSIONAMENTO
# ============================================================

def redimensionar_imagem(imagem):
    """
    Ajusta a resolução para OCR.

    Imagens pequenas são ampliadas.
    Imagens exageradamente grandes são reduzidas.
    """

    imagem = imagem.convert(
        "RGB"
    )

    largura, altura = imagem.size

    if largura < LARGURA_MINIMA:

        escala = (
            LARGURA_MINIMA
            / largura
        )

        nova_altura = int(
            altura * escala
        )

        imagem = imagem.resize(
            (
                LARGURA_MINIMA,
                nova_altura
            ),
            Image.Resampling.LANCZOS
        )

    elif largura > LARGURA_MAXIMA:

        escala = (
            LARGURA_MAXIMA
            / largura
        )

        nova_altura = int(
            altura * escala
        )

        imagem = imagem.resize(
            (
                LARGURA_MAXIMA,
                nova_altura
            ),
            Image.Resampling.LANCZOS
        )

    return imagem


# ============================================================
# PREPARAÇÃO BÁSICA
# ============================================================

def preparar_imagem(imagem):
    """
    Faz apenas o tratamento estrutural da imagem.

    Não executa OCR.
    """

    imagem = ImageOps.exif_transpose(
        imagem
    ).convert(
        "RGB"
    )

    imagem = redimensionar_imagem(
        imagem
    )

    return imagem


# ============================================================
# TRATAMENTO PARA OCR
# ============================================================

def preparar_para_ocr(imagem):
    """
    Cria a versão principal usada pelo OCR.

    Mantemos esse tratamento separado porque,
    posteriormente, documentos diferentes poderão
    receber tratamentos diferentes sem alterar
    o restante do sistema.
    """

    imagem = preparar_imagem(
        imagem
    )

    imagem = ImageOps.grayscale(
        imagem
    )

    imagem = ImageOps.autocontrast(
        imagem
    )

    imagem = ImageEnhance.Contrast(
        imagem
    ).enhance(
        1.35
    )

    imagem = imagem.filter(
        ImageFilter.SHARPEN
    )

    return imagem


# ============================================================
# VERSÃO EM ALTO CONTRASTE
# ============================================================

def preparar_alto_contraste(imagem):
    """
    Versão disponível para documentos apagados,
    fotografados ou com fundo ruim.

    Ainda NÃO será usada automaticamente nesta etapa.
    """

    imagem = preparar_imagem(
        imagem
    )

    imagem = ImageOps.grayscale(
        imagem
    )

    imagem = ImageOps.autocontrast(
        imagem
    )

    imagem = ImageEnhance.Contrast(
        imagem
    ).enhance(
        1.65
    )

    return imagem


# ============================================================
# VERSÃO BINÁRIA
# ============================================================

def preparar_binaria(
    imagem,
    limite=175
):
    """
    Cria uma imagem preto e branco.

    Pode ser útil posteriormente para determinados
    documentos ou digitalizações fracas.

    Ainda NÃO será usada automaticamente.
    """

    imagem = preparar_alto_contraste(
        imagem
    )

    imagem = imagem.point(
        lambda pixel:
        255
        if pixel > limite
        else 0
    )

    return imagem


# ============================================================
# PREPARAR ARQUIVO RECEBIDO
# ============================================================

def preparar_arquivo_imagem(
    arquivo_bytes
):
    """
    Recebe diretamente os bytes de JPG/JPEG/PNG
    e devolve a imagem preparada para OCR.

    Esta será a função chamada pelo app.py.
    """

    imagem_original = abrir_imagem(
        arquivo_bytes
    )

    try:

        imagem_processada = (
            preparar_para_ocr(
                imagem_original
            )
        )

        return imagem_processada

    finally:

        try:
            imagem_original.close()
        except Exception:
            pass

        del imagem_original

        gc.collect()


# ============================================================
# INFORMAÇÕES DA IMAGEM
# ============================================================

def obter_informacoes_imagem(
    arquivo_bytes
):
    """
    Retorna informações básicas sem executar OCR.
    Útil para diagnóstico.
    """

    imagem = abrir_imagem(
        arquivo_bytes
    )

    try:

        return {
            "largura":
                imagem.width,

            "altura":
                imagem.height,

            "modo":
                imagem.mode,

            "formato":
                (
                    imagem.format
                    if imagem.format
                    else "IMAGEM"
                )
        }

    finally:

        try:
            imagem.close()
        except Exception:
            pass

        del imagem

        gc.collect()


# ============================================================
# LIBERAÇÃO DE MEMÓRIA
# ============================================================

def liberar_imagem(imagem):
    """
    Fecha a imagem quando possível e força
    coleta de memória.

    Importante para lotes com muitos arquivos.
    """

    try:
        imagem.close()
    except Exception:
        pass

    try:
        del imagem
    except Exception:
        pass

    gc.collect()
