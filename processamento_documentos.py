import io
import gc
import numpy as np
from PIL import Image, ImageOps
import fitz
from rapidocr import RapidOCR

from extrator_documentos import extrair_campos_blocos


# ============================================================
# RAPIDOCR - UMA INSTÂNCIA POR PROCESSO
# ============================================================

_RAPIDOCR = None


def obter_rapidocr():
    global _RAPIDOCR
    if _RAPIDOCR is None:
        _RAPIDOCR = RapidOCR()
    return _RAPIDOCR


# ============================================================
# IMAGEM
# ============================================================

def preparar_imagem(imagem):
    """
    Mantém a imagem em RGB.
    Para ficar igual ao teste do VSCode, não aplica filtros pesados.
    """
    imagem = ImageOps.exif_transpose(imagem)
    return imagem.convert("RGB")


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


def resultado_para_blocos(resultado, largura, altura, pagina=1):
    """
    Gera EXATAMENTE a estrutura de blocos esperada pelo extrator do VSCode:
    texto, confiança, página, box e coordenadas relativas.
    """
    textos = getattr(resultado, "txts", None) or []
    scores = getattr(resultado, "scores", None) or []
    boxes = getattr(resultado, "boxes", None) or []

    blocos = []

    for i, valor in enumerate(textos):
        valor = str(valor or "").strip()
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

        bloco = {
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

            # Mantidos também para compatibilidade com telas/código antigo
            "x": 0.0,
            "y": 0.0,
        }

        if pos:
            bloco.update(pos)
            bloco["x_relativo"] = pos["centro_x"] / largura if largura else None
            bloco["y_relativo"] = pos["centro_y"] / altura if altura else None
            bloco["x"] = pos["centro_x"]
            bloco["y"] = pos["centro_y"]

        blocos.append(bloco)

    return blocos


def executar_ocr_imagem(imagem, pagina=1):
    """
    Mesmo princípio do VSCode: RapidOCR na imagem inteira e preservação
    da ordem original retornada pelo OCR.
    """
    imagem = preparar_imagem(imagem)
    largura, altura = imagem.size

    resultado = obter_rapidocr()(np.array(imagem))
    blocos = resultado_para_blocos(
        resultado,
        largura=largura,
        altura=altura,
        pagina=pagina,
    )

    texto = "\n".join(bloco["texto"] for bloco in blocos)
    gc.collect()
    return texto, blocos


# ============================================================
# PDF
# ============================================================

def extrair_texto_pdf(arquivo):
    """Mantido por compatibilidade; a leitura cadastral usa RapidOCR."""
    arquivo.seek(0)
    documento = fitz.open(stream=arquivo.getvalue(), filetype="pdf")
    partes = []

    for pagina in documento:
        partes.append(pagina.get_text("text") or "")

    documento.close()
    return "\n".join(partes).strip()


def pdf_tem_texto_util(texto):
    # Mantido apenas para compatibilidade com chamadas antigas.
    return bool(str(texto or "").strip())


def executar_ocr_pdf(arquivo):
    """
    Renderiza em 250 DPI, exatamente como o teste do VSCode que funcionou.
    Cada página mantém suas coordenadas relativas próprias.
    """
    arquivo.seek(0)
    documento = fitz.open(stream=arquivo.getvalue(), filetype="pdf")

    textos = []
    todos_blocos = []

    for numero_pagina in range(len(documento)):
        pagina = documento[numero_pagina]

        pix = pagina.get_pixmap(
            matrix=fitz.Matrix(250 / 72, 250 / 72),
            alpha=False,
        )

        # PNG preserva melhor caracteres pequenos do que JPEG.
        bytes_imagem = pix.tobytes("png")
        imagem = Image.open(io.BytesIO(bytes_imagem)).convert("RGB")

        texto, blocos = executar_ocr_imagem(
            imagem,
            pagina=numero_pagina + 1,
        )

        if texto:
            textos.append(texto)

        todos_blocos.extend(blocos)

        del imagem, pix, bytes_imagem
        gc.collect()

    documento.close()

    return "\n".join(textos), todos_blocos


# ============================================================
# LEITURA DO UPLOAD DO STREAMLIT
# ============================================================

def ler_documento(arquivo):
    """
    PDF e imagem passam pelo MESMO RapidOCR usado no VSCode.
    Não pula o OCR por existir camada de texto no PDF.
    """
    nome = str(getattr(arquivo, "name", "")).lower()

    if nome.endswith(".pdf"):
        texto, blocos = executar_ocr_pdf(arquivo)
        return texto, blocos, "PDF — OCR RapidOCR"

    arquivo.seek(0)
    imagem = Image.open(arquivo).convert("RGB")

    texto, blocos = executar_ocr_imagem(imagem, pagina=1)

    del imagem
    gc.collect()

    return texto, blocos, "Imagem — OCR RapidOCR"


# ============================================================
# EXTRAÇÃO
# ============================================================

def extrair_dados(texto, itens, tipo_leitura=None):
    """
    Interface mantida igual à usada pelo Streamlit.
    O argumento 'texto' continua existindo para não quebrar o app,
    mas a interpretação agora é feita pelos blocos RapidOCR, como no VSCode.
    """
    return extrair_campos_blocos(itens)


def extrair_dados_ocr(texto, itens):
    return extrair_campos_blocos(itens)


def dados_digitais_suficientes(dados):
    # Compatibilidade. O fluxo novo não usa atalho de PDF digital.
    return False
