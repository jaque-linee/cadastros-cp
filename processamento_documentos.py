import io
import gc
import numpy as np
from PIL import Image, ImageOps
import fitz
from rapidocr import RapidOCR

from extrator_documentos import extrair_dados_streamlit

_RAPIDOCR = None


def obter_rapidocr():
    global _RAPIDOCR
    if _RAPIDOCR is None:
        _RAPIDOCR = RapidOCR()
    return _RAPIDOCR


def preparar_imagem(imagem):
    imagem = ImageOps.exif_transpose(imagem)
    return imagem.convert("RGB")


def _box_dados(box):
    try:
        pts = [(float(p[0]), float(p[1])) for p in box]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        return None


def executar_ocr_imagem(imagem, pagina=1):
    """RapidOCR no MESMO formato de blocos usado pelo VSCode."""
    imagem = preparar_imagem(imagem)
    largura, altura = imagem.size
    resultado = obter_rapidocr()(np.array(imagem))

    textos = getattr(resultado, "txts", None) or []
    scores = getattr(resultado, "scores", None) or []
    boxes = getattr(resultado, "boxes", None) or []

    blocos = []
    for i, bruto in enumerate(textos):
        txt = str(bruto or "").strip()
        if not txt:
            continue

        try:
            conf = float(scores[i]) if i < len(scores) else 0.0
        except Exception:
            conf = 0.0

        box = boxes[i] if i < len(boxes) else None
        pos = _box_dados(box)

        bloco = {
            "texto": txt,
            "confianca": conf,
            "pagina": pagina,
            "largura_pagina": largura,
            "altura_pagina": altura,
            "box": box,
            "x_min": None, "y_min": None,
            "x_max": None, "y_max": None,
            "centro_x": None, "centro_y": None,
            "x_relativo": None, "y_relativo": None,
            "x": 0.0, "y": 0.0,
        }

        if pos:
            x1, y1, x2, y2 = pos
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            bloco.update({
                "x_min": x1, "y_min": y1,
                "x_max": x2, "y_max": y2,
                "centro_x": cx, "centro_y": cy,
                "x_relativo": cx / largura if largura else None,
                "y_relativo": cy / altura if altura else None,
                "x": cx, "y": cy,
            })

        blocos.append(bloco)

    # IMPORTANTE: não reordena. Mantém a ordem do RapidOCR igual ao VSCode.
    texto = "\n".join(b["texto"] for b in blocos)
    gc.collect()
    return texto, blocos


def extrair_texto_pdf(arquivo):
    arquivo.seek(0)
    doc = fitz.open(stream=arquivo.getvalue(), filetype="pdf")
    texto = "\n".join((p.get_text("text") or "") for p in doc)
    doc.close()
    return texto.strip()


def pdf_tem_texto_util(texto):
    return bool(str(texto or "").strip())


def executar_ocr_pdf(arquivo):
    arquivo.seek(0)
    doc = fitz.open(stream=arquivo.getvalue(), filetype="pdf")
    textos = []
    blocos = []

    for n in range(len(doc)):
        pagina = doc[n]
        pix = pagina.get_pixmap(matrix=fitz.Matrix(250/72, 250/72), alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        txt, bl = executar_ocr_imagem(img, pagina=n+1)
        if txt:
            textos.append(txt)
        blocos.extend(bl)
        del img, pix
        gc.collect()

    doc.close()
    return "\n".join(textos), blocos


def ler_documento(arquivo):
    """PDF ou imagem: sempre usa o RapidOCR, como no teste do VSCode."""
    nome = str(getattr(arquivo, "name", "")).lower()

    if nome.endswith(".pdf"):
        texto, blocos = executar_ocr_pdf(arquivo)
        return texto, blocos, "PDF — OCR"

    arquivo.seek(0)
    imagem = Image.open(arquivo)
    texto, blocos = executar_ocr_imagem(imagem, pagina=1)
    del imagem
    gc.collect()
    return texto, blocos, "Imagem — OCR"


def extrair_dados_ocr(texto, itens):
    return extrair_dados_streamlit(itens)


def extrair_dados_pdf_digital(texto):
    # Não usado no fluxo novo; mantido por compatibilidade.
    return {
        "nome":"", "cpf":"", "rg":"", "data_nascimento":"",
        "nome_mae":"", "endereco":"", "numero":"", "bairro":"",
        "cidade":"", "titulo":"", "zona":"", "secao":"",
        "telefone":"", "nis":"", "dap":"", "sus":""
    }


def dados_digitais_suficientes(dados):
    return False


def extrair_dados(texto, itens, tipo_leitura=None):
    return extrair_dados_streamlit(itens)
