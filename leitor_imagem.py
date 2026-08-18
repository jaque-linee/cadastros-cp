import gc

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def preparar_imagem(imagem):
    """
    Prepara JPG/PNG ou uma página de PDF já convertida em imagem
    para ser enviada ao OCR.

    Esta função NÃO faz OCR e NÃO extrai campos.
    Apenas melhora a imagem.
    """

    imagem = ImageOps.exif_transpose(imagem).convert("RGB")

    largura, altura = imagem.size

    # Aumenta imagens pequenas para melhorar a leitura
    if largura < 2000:
        escala = 2000 / largura

        imagem = imagem.resize(
            (
                2000,
                int(altura * escala)
            ),
            Image.Resampling.LANCZOS
        )

    # Evita imagens exageradamente grandes
    if imagem.width > 3000:
        escala = 3000 / imagem.width

        imagem = imagem.resize(
            (
                3000,
                int(imagem.height * escala)
            ),
            Image.Resampling.LANCZOS
        )

    return imagem


def preparar_para_ocr(imagem):
    """
    Faz o tratamento usado antes da leitura OCR.
    """

    imagem = preparar_imagem(imagem)

    imagem = ImageOps.grayscale(imagem)

    imagem = ImageOps.autocontrast(imagem)

    imagem = ImageEnhance.Contrast(
        imagem
    ).enhance(1.35)

    imagem = imagem.filter(
        ImageFilter.SHARPEN
    )

    return imagem


def liberar_imagem(imagem):
    """
    Ajuda a liberar memória durante processamento de lotes grandes.
    """

    try:
        del imagem
    except Exception:
        pass

    gc.collect()
