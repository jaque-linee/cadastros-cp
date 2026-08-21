import gc
import io
import os
import tempfile
import fitz
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from rapidocr import RapidOCR
from extrator_documentos import (
    extrair_dados as extrair_dados_blocos,
    extrair_telefone, parece_nome, sem_acentos, somente_numeros, formatar_telefone
)

def pdf_para_imagens_bytes(pdf_bytes, pasta):
    documento=fitz.open(stream=pdf_bytes,filetype="pdf")
    paginas=[]
    try:
        for numero,pagina in enumerate(documento):
            matriz=fitz.Matrix(250/72,250/72)
            pix=pagina.get_pixmap(matrix=matriz,alpha=False)
            caminho=os.path.join(pasta,f"pagina_{numero+1}.png")
            pix.save(caminho)
            paginas.append({"pagina":numero+1,"caminho":PathLike(caminho),"largura":pix.width,"altura":pix.height})
    finally:
        documento.close()
    return paginas

class PathLike(str):
    @property
    def name(self):
        return os.path.basename(self)

# ============================================================
# RAPIDOCR
# ============================================================

def criar_ocr():
    print()
    print("Carregando RapidOCR...")
    inicio = time.perf_counter()
    ocr = RapidOCR()
    print(f"RapidOCR carregado em {time.perf_counter() - inicio:.2f} segundos.")
    return ocr


def analisar_box(box):
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
            "centro_y": (min(ys) + max(ys)) / 2
        }
    except Exception:
        return None


def resultado_para_blocos(resultado, largura, altura, pagina=1, offset_x=0, offset_y=0):
    textos = getattr(resultado, "txts", None)
    scores = getattr(resultado, "scores", None)
    boxes = getattr(resultado, "boxes", None)

    if textos is None:
        return []

    scores = scores if scores is not None else []
    boxes = boxes if boxes is not None else []

    blocos = []

    for i, valor in enumerate(textos):
        valor = str(valor or "").strip()
        if not valor:
            continue

        conf = None
        if i < len(scores):
            try:
                conf = float(scores[i])
            except Exception:
                pass

        box = boxes[i] if i < len(boxes) else None
        pos = analisar_box(box)

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
            "y_relativo": None
        }

        if pos:
            bloco["x_min"] = pos["x_min"] + offset_x
            bloco["y_min"] = pos["y_min"] + offset_y
            bloco["x_max"] = pos["x_max"] + offset_x
            bloco["y_max"] = pos["y_max"] + offset_y
            bloco["centro_x"] = pos["centro_x"] + offset_x
            bloco["centro_y"] = pos["centro_y"] + offset_y
            bloco["x_relativo"] = bloco["centro_x"] / largura
            bloco["y_relativo"] = bloco["centro_y"] / altura

        blocos.append(bloco)

    return blocos


def executar_ocr(ocr, pagina):
    caminho = pagina["caminho"]
    largura = pagina["largura"]
    altura = pagina["altura"]

    print()
    print("=" * 70)
    print(f"LENDO: {caminho.name}")
    print("=" * 70)

    inicio = time.perf_counter()
    resultado = ocr(str(caminho))
    tempo = time.perf_counter() - inicio

    blocos = resultado_para_blocos(
        resultado,
        largura,
        altura,
        pagina["pagina"]
    )

    print()
    print(f"TEMPO DO OCR: {tempo:.2f} segundos")
    print()
    print("TEXTO ENCONTRADO:")
    print("-" * 70)

    for bloco in blocos:
        conf = bloco["confianca"]
        if conf is None:
            print(bloco["texto"])
        else:
            print(f"[{conf:.3f}] {bloco['texto']}")

    print("-" * 70)
    print(f"{len(blocos)} trecho(s) encontrados.")

    return blocos


# ============================================================
# RECUPERAÇÃO DO NOME DA MÃE
# ============================================================

def localizar_filiacao(blocos):
    for bloco in blocos:
        normal = sem_acentos(bloco["texto"])
        compacto = "".join(c for c in normal if c.isalnum())

        if "FILIACAO" in compacto or "FILIACA" in compacto:
            if bloco.get("x_min") is not None:
                return bloco

    return None


def preparar_recorte_mae(imagem):
    # O nome da Jackeline está legível; o problema é a resolução
    # efetiva que chega ao OCR. Aqui ampliamos somente o recorte.
    imagem = ImageOps.grayscale(imagem)
    imagem = ImageEnhance.Contrast(imagem).enhance(1.8)

    largura, altura = imagem.size
    imagem = imagem.resize(
        (largura * 2, altura * 2),
        Image.Resampling.LANCZOS
    )

    return imagem


def recuperar_nome_mae(ocr, caminho_imagem, blocos, nome_principal):
    ancora = localizar_filiacao(blocos)

    if ancora is None:
        return ""

    imagem = Image.open(caminho_imagem).convert("RGB")
    largura, altura = imagem.size

    x1 = int(ancora["x_min"])
    y1 = int(ancora["y_min"])
    x2_rotulo = int(ancora["x_max"])
    y2_rotulo = int(ancora["y_max"])

    # Não é posição fixa da página.
    # A área nasce da posição onde FILIAÇÃO foi encontrada.
    #
    # Criamos duas hipóteses porque alguns documentos colocam
    # os nomes abaixo do rótulo e outros à direita.
    margem_x = max(40, int(largura * 0.015))
    margem_y = max(25, int(altura * 0.010))

    recortes = []

    # Hipótese A: nomes abaixo de FILIAÇÃO.
    recortes.append((
        max(0, x1 - margem_x),
        max(0, y1 - margem_y),
        min(largura, x1 + int(largura * 0.52)),
        min(altura, y2_rotulo + int(altura * 0.18))
    ))

    # Hipótese B: nomes à direita de FILIAÇÃO.
    recortes.append((
        max(0, x1 - margem_x),
        max(0, y1 - int(altura * 0.04)),
        min(largura, x2_rotulo + int(largura * 0.55)),
        min(altura, y2_rotulo + int(altura * 0.12))
    ))

    melhores = []

    for numero, caixa in enumerate(recortes, start=1):
        crop = imagem.crop(caixa)
        crop = preparar_recorte_mae(crop)

        inicio = time.perf_counter()
        resultado = ocr(np.array(crop))
        tempo = time.perf_counter() - inicio

        textos = getattr(resultado, "txts", None) or []
        scores = getattr(resultado, "scores", None) or []

        nomes = []

        for i, valor in enumerate(textos):
            valor = str(valor or "").strip()

            if not parece_nome(valor):
                continue

            normal = sem_acentos(valor)

            if nome_principal and normal == sem_acentos(nome_principal):
                continue

            if any(t in normal for t in [
                "FILIACAO", "ASSINATURA", "PORTADOR",
                "NACIONALIDADE", "CPF", "IDENTIDADE",
                "VALIDADE", "NASCIMENTO"
            ]):
                continue

            conf = 0.0
            if i < len(scores):
                try:
                    conf = float(scores[i])
                except Exception:
                    pass

            nomes.append((conf, valor.upper()))

        print(
            f"Recuperação da mãe - tentativa {numero}: "
            f"{tempo:.2f}s | candidatos: {[n[1] for n in nomes]}"
        )

        # Em FILIAÇÃO, quando aparecem dois nomes, usamos o segundo.
        if len(nomes) >= 2:
            melhores.append((sum(n[0] for n in nomes[:2]), nomes[1][1]))
        elif len(nomes) == 1:
            melhores.append((nomes[0][0] - 0.20, nomes[0][1]))

    if not melhores:
        return ""

    melhores.sort(key=lambda x: x[0], reverse=True)
    return melhores[0][1]


# ============================================================
# RECUPERAÇÃO DO TELEFONE
# ============================================================

def telefone_plausivel(numero):
    numero = somente_numeros(numero)

    if len(numero) == 11:
        # DDD + celular.
        ddd = int(numero[:2])
        return 11 <= ddd <= 99 and numero[2] == "9"

    if len(numero) == 10:
        # DDD + telefone fixo.
        ddd = int(numero[:2])
        return 11 <= ddd <= 99 and numero[2] in "2345"

    return False


def recuperar_telefone(ocr, caminho_imagem, blocos, cpf, titulo, rg):
    imagem = Image.open(caminho_imagem).convert("RGB")

    # Segunda leitura somente quando o telefone normal faltou.
    # Não usa posição fixa: examina a página inteira, mas numa
    # versão leve, otimizada para números escritos/anotados.
    cinza = ImageOps.grayscale(imagem)
    cinza = ImageEnhance.Contrast(cinza).enhance(1.65)

    largura, altura = cinza.size

    # Não aumentamos uma página que já é grande; isso segura o tempo.
    if largura < 2200:
        fator = 2200 / largura
        cinza = cinza.resize(
            (int(largura * fator), int(altura * fator)),
            Image.Resampling.LANCZOS
        )

    inicio = time.perf_counter()
    resultado = ocr(np.array(cinza))
    tempo = time.perf_counter() - inicio

    textos = getattr(resultado, "txts", None) or []
    scores = getattr(resultado, "scores", None) or []

    proibidos = {
        somente_numeros(cpf),
        somente_numeros(titulo),
        somente_numeros(rg)
    }

    # CEPs já reconhecidos no OCR principal.
    for bloco in blocos:
        normal = sem_acentos(bloco["texto"])
        if "CEP" in normal:
            proibidos.add(somente_numeros(bloco["texto"]))

    candidatos = []

    for i, valor in enumerate(textos):
        valor = str(valor or "").strip()
        numero = somente_numeros(valor)

        if numero in proibidos:
            continue

        if not telefone_plausivel(numero):
            continue

        conf = 0.0
        if i < len(scores):
            try:
                conf = float(scores[i])
            except Exception:
                pass

        pontos = conf

        if "-" in valor:
            pontos += 0.20
        if "(" in valor or ")" in valor:
            pontos += 0.15

        candidatos.append((pontos, numero, valor))

    print(
        f"Recuperação do telefone: {tempo:.2f}s | "
        f"candidatos: {[c[2] for c in candidatos]}"
    )

    if not candidatos:
        return ""

    candidatos.sort(key=lambda x: x[0], reverse=True)
    return formatar_telefone(candidatos[0][1])



def _bytes_arquivo(arquivo):
    if isinstance(arquivo,(bytes,bytearray)):
        return bytes(arquivo)
    try: arquivo.seek(0)
    except Exception: pass
    dados=arquivo.read()
    try: arquivo.seek(0)
    except Exception: pass
    return dados

def ler_documento(arquivo):
    nome=str(getattr(arquivo,"name","arquivo.pdf") or "arquivo.pdf").lower()
    dados_arquivo=_bytes_arquivo(arquivo)
    ocr=criar_ocr()
    with tempfile.TemporaryDirectory() as pasta:
        if nome.endswith(".pdf"):
            paginas=pdf_para_imagens_bytes(dados_arquivo,pasta)
            tipo="PDF — OCR"
        elif nome.endswith((".jpg",".jpeg",".png")):
            img=Image.open(io.BytesIO(dados_arquivo)).convert("RGB")
            caminho=os.path.join(pasta,"pagina_1.png"); img.save(caminho,"PNG")
            paginas=[{"pagina":1,"caminho":PathLike(caminho),"largura":img.width,"altura":img.height}]
            img.close(); tipo="Imagem — OCR"
        else:
            raise ValueError("Formato não suportado. Use PDF, JPG, JPEG ou PNG.")
        blocos=[]
        for pagina in paginas:
            blocos.extend(executar_ocr(ocr,pagina))
        recuperados={}
        if blocos:
            iniciais=extrair_dados_blocos(blocos)
            if paginas:
                mae=recuperar_nome_mae(ocr,paginas[0]["caminho"],blocos,iniciais.get("NOME",""))
                if mae: recuperados["NOME DA MÃE"]=mae
            if not iniciais.get("TELEFONE","") and paginas:
                tel=recuperar_telefone(ocr,paginas[0]["caminho"],blocos,iniciais.get("CPF",""),iniciais.get("TITULO",""),iniciais.get("RG",""))
                if tel: recuperados["TELEFONE"]=tel
        blocos.append({"_tipo":"RECUPERADOS","_recuperados":recuperados,"texto":"","confianca":0.0,"pagina":0,"x_relativo":None,"y_relativo":None})
        texto="\n".join(b.get("texto","") for b in blocos if b.get("texto"))
    gc.collect()
    return texto,blocos,tipo

def extrair_dados(texto,itens,tipo_leitura):
    recuperados={}; blocos=[]
    for item in list(itens or []):
        if isinstance(item,dict) and item.get("_tipo")=="RECUPERADOS":
            recuperados.update(item.get("_recuperados") or {})
        else:
            blocos.append(item)
    d=extrair_dados_blocos(blocos,recuperados=recuperados)
    return {
        "nome":d.get("NOME",""),"cpf":d.get("CPF",""),"rg":d.get("RG",""),
        "data_nascimento":d.get("DATA DE NASCIMENTO",""),"nome_mae":d.get("NOME DA MÃE",""),
        "endereco":d.get("ENDEREÇO",""),"numero":d.get("Nº",""),"bairro":d.get("BAIRRO",""),
        "cidade":d.get("CIDADE",""),"titulo":d.get("TITULO",""),"zona":d.get("ZONA",""),
        "secao":d.get("SEÇÃO",""),"telefone":d.get("TELEFONE","")
    }
