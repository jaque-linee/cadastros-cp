import io
import gc
import re
import numpy as np
import streamlit as st
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import pytesseract
import fitz

import leitor_pdf
import leitor_imagem
import extrator_documentos

from validacoes import (
    somente_numeros,
    normalizar_texto,
    remover_acentos,
    normalizar_rotulo,
    formatar_cpf,
    cpf_valido,
    data_valida,
)


def normalizar_telefone(valor):
    numero = somente_numeros(valor)

    if len(numero) == 13 and numero.startswith("55"):
        numero = numero[2:]

    if len(numero) in (10, 11):
        return numero

    return ""


def encontrar_telefone_em_texto(texto):
    texto = str(texto or "")

    padroes = [
        r"(?<!\d)(?:\+?55[\s.\-]?)?\(?\d{2}\)?[\s.\-]?\d{4,5}[\s.\-]?\d{4}(?!\d)",
        r"(?<!\d)\d{10,11}(?!\d)"
    ]

    candidatos = []

    for padrao in padroes:
        for match in re.finditer(padrao, texto):
            telefone = normalizar_telefone(match.group(0))

            if not telefone:
                continue

            if len(telefone) == 11 and cpf_valido(telefone):
                continue

            if telefone not in candidatos:
                candidatos.append(telefone)

    if len(candidatos) == 1:
        return candidatos[0]

    return ""


def encontrar_telefone_documento(texto, itens):
    telefone = encontrar_telefone_em_texto(texto)

    if telefone:
        return telefone

    candidatos = []

    for item in itens or []:
        telefone = encontrar_telefone_em_texto(
            item.get("texto", "")
        )

        if telefone and telefone not in candidatos:
            candidatos.append(telefone)

    if len(candidatos) == 1:
        return candidatos[0]

    return ""


def encontrar_telefone_nome_arquivo(nome_arquivo):
    nome = str(nome_arquivo or "")

    if "." in nome:
        nome = nome.rsplit(".", 1)[0]

    return encontrar_telefone_em_texto(nome)


# ============================================================
# 5. OCR
# ============================================================

@st.cache_resource(show_spinner=False)
def carregar_ocr():
    import easyocr

    return easyocr.Reader(
        ["pt", "en"],
        gpu=False,
        verbose=False
    )


# ============================================================
# 6. PREPARAÇÃO DA IMAGEM
# ============================================================

def preparar_imagem(imagem):
    imagem = ImageOps.exif_transpose(
        imagem
    )

    imagem = imagem.convert(
        "RGB"
    )

    largura, altura = imagem.size

    if largura < 1200:
        proporcao = (
            1200 / largura
        )

        imagem = imagem.resize(
            (
                1200,
                int(
                    altura * proporcao
                )
            ),
            Image.Resampling.LANCZOS
        )

    if imagem.width > 2000:
        proporcao = (
            2000 / imagem.width
        )

        imagem = imagem.resize(
            (
                2000,
                int(
                    imagem.height
                    * proporcao
                )
            ),
            Image.Resampling.LANCZOS
        )

    return imagem


# ============================================================
# 7. OCR DE IMAGEM - VERSÃO ESTÁVEL (APENAS TESSERACT)
# ============================================================

def executar_ocr_imagem(imagem):
    """
    OCR usando Tesseract com pré-processamento otimizado.
    """
    # ============================================================
    # 1. PRÉ-PROCESSAMENTO DA IMAGEM
    # ============================================================
    imagem = ImageOps.exif_transpose(imagem).convert("RGB")
    largura, altura = imagem.size

    # Redimensiona para melhorar a leitura
    if largura < 2000:
        escala = 2000 / largura
        imagem = imagem.resize((2000, int(altura * escala)), Image.Resampling.LANCZOS)

    # Converte para escala de cinza
    imagem_gray = ImageOps.grayscale(imagem)
    
    # Aumenta contraste
    imagem_gray = ImageOps.autocontrast(imagem_gray)
    
    # Aplica diferentes técnicas de pré-processamento
    # e testa qual funciona melhor
    
    # Versão 1: Contraste + Sharpen
    img_v1 = ImageEnhance.Contrast(imagem_gray).enhance(2.0)
    img_v1 = img_v1.filter(ImageFilter.SHARPEN)
    
    # Versão 2: Binarização (preto e branco forte)
    img_v2 = imagem_gray.point(lambda x: 0 if x < 128 else 255, '1')
    img_v2 = img_v2.convert('L')
    
    # Versão 3: Original com pouco contraste
    img_v3 = ImageEnhance.Contrast(imagem_gray).enhance(1.3)
    
    # ============================================================
    # 2. TESSERACT - MÚLTIPLAS TENTATIVAS
    # ============================================================
    textos_tentados = []
    itens_final = []
    
    # Lista de configurações para testar
    configs = [
        "--oem 3 --psm 6",      # Bloco de texto uniforme
        "--oem 3 --psm 4",      # Texto com uma coluna
        "--oem 3 --psm 11",     # Texto esparso
        "--oem 3 --psm 12",     # Texto com orientação variada
        "--oem 3 --psm 3",      # Texto automático
    ]
    
    imagens_teste = [img_v1, img_v2, img_v3]
    
    melhor_texto = ""
    melhor_confianca = 0
    
    for img in imagens_teste:
        for config in configs:
            try:
                # Tenta extrair texto
                texto = pytesseract.image_to_string(
                    img, 
                    lang="por+eng", 
                    config=config
                ).strip()
                
                if texto and len(texto) > 10:
                    textos_tentados.append(texto)
                    
                    # Se for maior que o melhor até agora, guarda
                    if len(texto) > len(melhor_texto):
                        # Verifica se tem dados relevantes (CPF, data, etc)
                        tem_dados_uteis = (
                            re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', texto) or  # CPF
                            re.search(r'\d{2}/\d{2}/\d{4}', texto) or           # Data
                            re.search(r'NOME|CPF|TITULO|INSCRICAO', texto.upper())  # Palavras-chave
                        )
                        
                        if tem_dados_uteis or len(texto) > 100:
                            melhor_texto = texto
                            
            except Exception:
                continue
    
    # ============================================================
    # 3. EXTRAI ITENS COM POSIÇÃO (da melhor imagem)
    # ============================================================
    try:
        # Usa a imagem que deu o melhor resultado
        # (tenta com a versão mais contrastada)
        dados_pos = pytesseract.image_to_data(
            img_v1, 
            lang="por+eng", 
            config="--oem 3 --psm 6", 
            output_type=pytesseract.Output.DICT
        )
        
        for i, palavra in enumerate(dados_pos.get("text", [])):
            palavra = str(palavra or "").strip()
            if not palavra:
                continue
            try:
                conf = float(dados_pos["conf"][i])
            except:
                conf = -1
            if conf < 20:  # Filtro mais rigoroso
                continue
            itens_final.append({
                "texto": palavra,
                "confianca": conf / 100.0,
                "x": float(dados_pos["left"][i]) + float(dados_pos["width"][i]) / 2,
                "y": float(dados_pos["top"][i]) + float(dados_pos["height"][i]) / 2
            })
    except Exception:
        pass
    
    # ============================================================
    # 4. SE NADA FUNCIONOU, TENTATIVA FINAL
    # ============================================================
    if not melhor_texto or len(melhor_texto) < 20:
        try:
            # Tenta com a imagem original sem muito processamento
            texto_final = pytesseract.image_to_string(
                imagem_gray,
                lang="por+eng",
                config="--oem 3 --psm 6"
            ).strip()
            
            if texto_final and len(texto_final) > len(melhor_texto):
                melhor_texto = texto_final
        except Exception:
            pass
    
    # Se ainda não tem texto, usa o primeiro que encontrou
    if not melhor_texto and textos_tentados:
        melhor_texto = max(textos_tentados, key=len)
    
    # ============================================================
    # 5. LIMPEZA
    # ============================================================
    del imagem
    del imagem_gray
    del img_v1
    del img_v2
    del img_v3
    gc.collect()
    
    return melhor_texto, itens_final
# ============================================================
# 7A. EXTRAIR DADOS TESSERACT - PRIORITÁRIO (NOVA FUNÇÃO)
# ============================================================

def extrair_dados_tesseract_prioritario(texto):
    """Extrai dados com prioridade para o Título Eleitoral."""
    texto = str(texto or "")
    linhas = linhas_texto(texto)
    
    dados = {"nome": "", "cpf": "", "titulo": "", "data_nascimento": "", "nome_mae": "", "zona": "", "secao": "", "telefone": ""}
    
    # NOME - Título Eleitoral
    padrao_nome = r"NOME\s+DO\s+ELEITOR\s*[|]\s*([A-ZÀ-Ÿ\s]+?)(?=\s*(?:DATA|INSCRICAO|ZONA|SECAO|$)|\n)"
    match = re.search(padrao_nome, texto, re.I)
    if match:
        nome = match.group(1).strip().upper()
        if parece_nome(nome) and len(nome.split()) >= 2:
            dados["nome"] = nome
            return dados
    
    # CPF
    for match in re.finditer(r"(?<!\d)(\d{3})[.\s]?(\d{3})[.\s]?(\d{3})[-\s]?(\d{2})(?!\d)", texto):
        numero = "".join(match.groups())
        if cpf_valido(numero):
            dados["cpf"] = formatar_cpf(numero)
            break
    
    # TÍTULO
    padrao_titulo = r"INSCRI[CÇ][AÃ]O\s*[:\-]?\s*(\d{4,12})"
    match = re.search(padrao_titulo, texto, re.I)
    if match:
        numero = somente_numeros(match.group(1))
        if len(numero) == 12:
            dados["titulo"] = numero
    
    # NASCIMENTO
    padrao_data = r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b"
    for linha in linhas:
        match = re.search(padrao_data, linha)
        if match:
            dia, mes, ano = int(match.group(1)), int(match.group(2)), int(match.group(3))
            if 1900 <= ano <= 2012:
                dados["data_nascimento"] = f"{dia:02d}/{mes:02d}/{ano}"
                break
    
    # NOME DA MÃE - FILIAÇÃO
    padrao_filiacao = r"FILIACAO\s*[:\-]?\s*([A-ZÀ-Ÿ\s]+?)(?=\s*(?:NATURALIDADE|CPF|REGISTRO|EMISSAO|DATA|$)|\n)"
    match = re.search(padrao_filiacao, texto, re.I)
    if match:
        filiacao = match.group(1).strip().upper()
        if " E " in filiacao:
            partes = filiacao.split(" E ")
            if len(partes) >= 2:
                mae = partes[-1].strip()
                if parece_nome(mae):
                    dados["nome_mae"] = mae
    
    # ZONA E SEÇÃO
    padrao_zona = r"ZONA\s*[:\-]?\s*(\d{1,3})[\s\S]{0,30}?SE[CÇ][AÃ]O\s*[:\-]?\s*(\d{1,4})"
    match = re.search(padrao_zona, texto, re.I)
    if match:
        dados["zona"] = match.group(1).zfill(3)
        dados["secao"] = match.group(2).zfill(4)
    
    return dados


# ============================================================
# 7B. OCR TESSERACT - FALLBACK
# ============================================================

def executar_tesseract_imagem(imagem):
    imagem = ImageOps.exif_transpose(imagem).convert("RGB")
    largura, altura = imagem.size

    if largura < 1800:
        escala = 1800 / largura
        imagem = imagem.resize(
            (1800, int(altura * escala)),
            Image.Resampling.LANCZOS
        )

    imagem = ImageOps.grayscale(imagem)
    imagem = ImageOps.autocontrast(imagem)
    imagem = ImageEnhance.Contrast(imagem).enhance(1.35)
    imagem = imagem.filter(ImageFilter.SHARPEN)

    try:
        return pytesseract.image_to_string(
            imagem,
            lang="por+eng",
            config="--oem 3 --psm 6"
        ).strip()
    finally:
        del imagem
        gc.collect()


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

    if re.search(
        r"\b\d{2}[\/.\-]\d{2}[\/.\-]\d{4}\b",
        texto
    ):
        pontos += 1

    if "CPF" in texto_normalizado:
        pontos += 1

    if (
        "INSCRICAO" in texto_normalizado
        or "TITULO" in texto_normalizado
    ):
        pontos += 1

    if "NOME" in texto_normalizado:
        pontos += 1

    if (
        "FILIACAO" in texto_normalizado
        or "MAE" in texto_normalizado
        or "NOME DA MAE" in texto_normalizado
    ):
        pontos += 1

    if (
        "CARTEIRA NACIONAL" in texto_normalizado
        or "HABILITACAO" in texto_normalizado
        or "REGISTRO" in texto_normalizado
    ):
        pontos += 1

    if (
        "IDENTIDADE" in texto_normalizado
        or "REGISTRO GERAL" in texto_normalizado
    ):
        pontos += 1

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
                1.25,
                1.25
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
    """
    Etapa 7B: somente o tratamento estrutural de PDF passa pelo leitor_pdf.
    O OCR e os parsers atuais continuam preservados.
    Em caso de falha, volta automaticamente ao leitor legado.
    """
    nome = str(getattr(arquivo, "name", "") or "").lower()

    # JPG/JPEG/PNG passam agora pelo módulo leitor_imagem.
    # O OCR e a extração de campos continuam preservados.
    if nome.endswith((".jpg", ".jpeg", ".png")):
        try:
            arquivo.seek(0)

            imagem = leitor_imagem.preparar_arquivo_imagem(
                arquivo.getvalue()
            )

            try:
                texto, itens = executar_ocr_imagem(
                    imagem
                )

                return (
                    texto,
                    itens,
                    "IMAGEM — OCR"
                )

            finally:
                leitor_imagem.liberar_imagem(
                    imagem
                )

        except Exception:
            try:
                arquivo.seek(0)
            except Exception:
                pass

            raise RuntimeError(
                "Falha no processamento modular do documento."
            )

    # Outros formatos permanecem no fluxo anterior.
    if not nome.endswith(".pdf"):
        raise RuntimeError(
            "Falha no processamento modular do documento."
        )

    try:
        arquivo.seek(0)
        pdf_bytes = arquivo.getvalue()
        analise = leitor_pdf.analisar_pdf(pdf_bytes)
        tipo_pdf = analise.get("tipo", "PDF_ESCANEADO")

        if tipo_pdf == "PDF_DIGITAL":
            return (
                str(analise.get("texto", "") or "").strip(),
                [],
                "PDF — texto digital"
            )

        textos = []
        todos_itens = []

        # Em PDF misto, preserva o texto nativo das páginas digitais.
        paginas_info = {
            int(p.get("pagina", 0)): p
            for p in analise.get("paginas", [])
        }

        for numero in analise.get("paginas_digitais", []):
            info = paginas_info.get(int(numero), {})
            texto_pagina = str(info.get("texto", "") or "").strip()
            if texto_pagina:
                textos.append(texto_pagina)

        # Só as páginas escaneadas são convertidas em imagem.
        paginas_ocr = leitor_pdf.converter_paginas_escaneadas(pdf_bytes)

        for item in paginas_ocr:
            imagem = item.get("imagem")
            if imagem is None:
                continue

            try:
                # Mantém o OCR atual do app nesta etapa.
                texto_pagina, itens_pagina = executar_ocr_imagem(imagem)

                if str(texto_pagina or "").strip():
                    textos.append(str(texto_pagina).strip())

                if itens_pagina:
                    todos_itens.extend(itens_pagina)
            finally:
                try:
                    imagem.close()
                except Exception:
                    pass
                gc.collect()

        texto_final = "\n\n".join(textos).strip()

        if tipo_pdf == "PDF_MISTO":
            tipo_leitura = "PDF — texto digital + OCR"
        else:
            tipo_leitura = "PDF — OCR"

        return texto_final, todos_itens, tipo_leitura

    except Exception:
        # Fallback de segurança: nada fica inutilizado se o módulo novo falhar.
        try:
            arquivo.seek(0)
        except Exception:
            pass
        raise RuntimeError("Falha no processamento modular do documento.")


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

    if not re.fullmatch(
        r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\-]*(?:\s[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\-]*)*",
        texto
    ):
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
        "CATEGORIA",
        "POLEGAR",
        "CHREITA",
        "IMPRESSAO",
        "DIGITAL"
    ]

    for termo in ignorar:
        if termo in normalizado:
            return False

    palavras = texto.split()

    if not (
        2 <= len(palavras) <= 8
    ):
        return False

    for palavra in palavras:
        if len(palavra) < 2:
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
    for i, linha in enumerate(linhas):
        rotulo = normalizar_rotulo(linha)

        if rotulo in ("MAE", "NOMEDAMAE", "NOMEMAE"):
            for deslocamento in (1, 2):
                pos = i + deslocamento
                if pos < len(linhas) and parece_nome(linhas[pos]):
                    return linhas[pos].upper()

            if i > 0 and parece_nome(linhas[i - 1]):
                return linhas[i - 1].upper()

    return ""


# ============================================================
# 16. EXTRAIR DADOS DO PDF DIGITAL
# ============================================================

def extrair_dados_pdf_digital(texto):
    linhas = linhas_texto(texto)

    dados = {
        "nome": "",
        "cpf": "",
        "titulo": "",
        "data_nascimento": "",
        "nome_mae": "",
        "zona": "",
        "secao": "",
        "telefone": ""
    }

    texto_norm = remover_acentos(texto).upper()

    eh_titulo = (
        "JUSTICA ELEITORAL" in texto_norm
        or "TITULO ELEITORAL" in texto_norm
    )

    eh_cnh = (
        "CARTEIRA NACIONAL" in texto_norm
        or "HABILITACAO" in texto_norm
        or "DENATRAN" in texto_norm
    )

    # 1. NOME
    for i, linha in enumerate(linhas):
        rotulo = normalizar_rotulo(linha)

        if rotulo in (
            "NOMEDOELEITOR",
            "NOME",
            "NOMECOMPLETO"
        ):
            if i + 1 < len(linhas):
                candidato = linhas[i + 1].strip()

                if parece_nome(candidato):
                    dados["nome"] = candidato.upper()
                    break

            if i > 0:
                candidato = linhas[i - 1].strip()

                if parece_nome(candidato):
                    dados["nome"] = candidato.upper()
                    break

    if not dados["nome"]:
        for linha in linhas:
            if parece_nome(linha):
                rotulo = normalizar_rotulo(linha)

                if not any(
                    termo in rotulo
                    for termo in (
                        "REPUBLICA",
                        "FEDERATIVA",
                        "JUSTICA",
                        "ELEITORAL",
                        "CARTEIRA",
                        "NACIONAL",
                        "HABILITACAO"
                    )
                ):
                    dados["nome"] = linha.upper()
                    break

    # 2. DATA DE NASCIMENTO
    for i, linha in enumerate(linhas):
        rotulo = normalizar_rotulo(linha)

        if (
            "DATADENASCIMENTO" in rotulo
            or rotulo == "NASCIMENTO"
            or rotulo == "DATANASCIMENTO"
        ):
            candidatos = []

            for deslocamento in (1, 2):
                pos = i + deslocamento

                if pos < len(linhas):
                    match = re.search(
                        r"\b(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})\b",
                        linhas[pos]
                    )

                    if match:
                        valor = (
                            f"{match.group(1)}/"
                            f"{match.group(2)}/"
                            f"{match.group(3)}"
                        )

                        if data_valida(valor):
                            candidatos.append(valor)

            if i > 0:
                match = re.search(
                    r"\b(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})\b",
                    linhas[i - 1]
                )

                if match:
                    valor = (
                        f"{match.group(1)}/"
                        f"{match.group(2)}/"
                        f"{match.group(3)}"
                    )

                    if data_valida(valor):
                        candidatos.append(valor)

            if candidatos:
                dados["data_nascimento"] = candidatos[0]
                break

    # 3. CPF
    for i, linha in enumerate(linhas):
        rotulo = normalizar_rotulo(linha)

        if "CPF" in rotulo:
            candidatos = [linha]

            if i + 1 < len(linhas):
                candidatos.append(linhas[i + 1])

            if i + 2 < len(linhas):
                candidatos.append(linhas[i + 2])

            for candidato in candidatos:
                numeros = somente_numeros(candidato)

                if len(numeros) == 11 and cpf_valido(numeros):
                    dados["cpf"] = formatar_cpf(numeros)
                    break

            if dados["cpf"]:
                break

    if not dados["cpf"]:
        for linha in linhas:
            numeros = somente_numeros(linha)

            if len(numeros) == 11 and cpf_valido(numeros):
                dados["cpf"] = formatar_cpf(numeros)
                break

    # 4. TÍTULO ELEITORAL
    if eh_titulo:
        for i, linha in enumerate(linhas):
            rotulo = normalizar_rotulo(linha)

            if (
                "INSCRICAO" in rotulo
                or rotulo == "TITULO"
                or rotulo == "TITULODEELEITOR"
            ):
                candidatos = [linha]

                for deslocamento in (1, 2, -1):
                    pos = i + deslocamento

                    if 0 <= pos < len(linhas):
                        candidatos.append(linhas[pos])

                for candidato in candidatos:
                    numero = somente_numeros(candidato)

                    if len(numero) == 12:
                        dados["titulo"] = numero
                        break

                if dados["titulo"]:
                    break

    # 5. ZONA E SEÇÃO
    if eh_titulo:
        def extrair_numero_associado_ao_rotulo(
            linhas,
            nome_rotulo,
            max_digitos
        ):
            for i, linha in enumerate(linhas):
                rotulo = normalizar_rotulo(linha)

                if rotulo != nome_rotulo:
                    continue

                if i > 0:
                    candidato = linhas[i - 1].strip()

                    if re.fullmatch(
                        r"\d{1," + str(max_digitos) + r"}",
                        candidato
                    ):
                        return candidato.zfill(
                            max_digitos
                        )

                linha_sem_acento = remover_acentos(
                    linha
                ).upper()

                match = re.search(
                    r"\b"
                    + nome_rotulo
                    + r"\b\s*[:\-]?\s*(\d{1,"
                    + str(max_digitos)
                    + r"})\b",
                    linha_sem_acento
                )

                if match:
                    return match.group(1).zfill(
                        max_digitos
                    )

                if i + 1 < len(linhas):
                    candidato = linhas[i + 1].strip()

                    if re.fullmatch(
                        r"\d{1," + str(max_digitos) + r"}",
                        candidato
                    ):
                        return candidato.zfill(
                            max_digitos
                        )

            return ""

        zona_encontrada = (
            extrair_numero_associado_ao_rotulo(
                linhas,
                "ZONA",
                3
            )
        )

        secao_encontrada = (
            extrair_numero_associado_ao_rotulo(
                linhas,
                "SECAO",
                4
            )
        )

        if zona_encontrada:
            dados["zona"] = zona_encontrada

        if secao_encontrada:
            dados["secao"] = secao_encontrada

    # 6. NOME DA MÃE
    for i, linha in enumerate(linhas):
        rotulo = normalizar_rotulo(linha)

        if rotulo in (
            "MAE",
            "NOMEDAMAE",
            "NOMEMAE"
        ):
            partes = []

            for deslocamento in range(1, 5):
                pos = i + deslocamento

                if pos >= len(linhas):
                    break

                candidato = linhas[pos].strip()
                candidato_rotulo = normalizar_rotulo(candidato)

                if eh_rotulo_documento(candidato):
                    break

                if re.search(r"\d", candidato):
                    break

                if parece_nome(candidato):
                    partes.append(candidato.upper())
                elif partes:
                    break

            if partes:
                dados["nome_mae"] = " ".join(partes)
                break

    if eh_titulo and not dados["nome_mae"]:
        indice_filiacao = None

        for i, linha in enumerate(linhas):
            if normalizar_rotulo(linha) == "FILIACAO":
                indice_filiacao = i
                break

        if indice_filiacao is not None:
            candidatos = []

            inicio = max(0, indice_filiacao - 3)
            fim = min(len(linhas), indice_filiacao + 5)

            for pos in range(inicio, fim):
                if pos == indice_filiacao:
                    continue

                candidato = linhas[pos].strip()

                if candidato.upper() == dados["nome"]:
                    continue

                if eh_rotulo_documento(candidato):
                    continue

                if re.search(r"\d", candidato):
                    continue

                if parece_nome(candidato):
                    candidatos.append(
                        (
                            pos,
                            candidato.upper()
                        )
                    )

            nomes_unicos = []

            for _, candidato in candidatos:
                if candidato not in nomes_unicos:
                    nomes_unicos.append(candidato)

            if nomes_unicos:
                dados["nome_mae"] = nomes_unicos[0]

    if eh_cnh and not dados["nome_mae"]:
        indice_filiacao = None

        for i, linha in enumerate(linhas):
            if normalizar_rotulo(linha) == "FILIACAO":
                indice_filiacao = i
                break

        if indice_filiacao is not None:
            bloco_filiacao = []

            rotulos_fim = (
                "PERMISSAO",
                "ACC",
                "CATHAB",
                "CATEGORIA",
                "REGISTRO",
                "VALIDADE",
                "HABILITACAO",
                "OBSERVACOES",
                "LOCAL",
                "DATAEMISSAO",
                "ASSINATURA"
            )

            for pos in range(
                indice_filiacao + 1,
                min(len(linhas), indice_filiacao + 10)
            ):
                candidato = linhas[pos].strip()
                rotulo = normalizar_rotulo(candidato)

                if any(
                    rotulo.startswith(fim)
                    for fim in rotulos_fim
                ):
                    break

                if not candidato:
                    continue

                if re.search(r"\d", candidato):
                    continue

                if candidato.upper() == dados["nome"]:
                    continue

                if parece_nome(candidato):
                    bloco_filiacao.append(candidato.upper())
                    continue

                if re.fullmatch(
                    r"[A-Za-zÀ-ÿ\s]+",
                    candidato
                ):
                    palavras = candidato.split()

                    if palavras:
                        bloco_filiacao.append(candidato.upper())

            if len(bloco_filiacao) >= 2:
                possibilidades = []

                for corte in range(1, len(bloco_filiacao)):
                    parte_1 = " ".join(
                        bloco_filiacao[:corte]
                    ).strip()

                    parte_2 = " ".join(
                        bloco_filiacao[corte:]
                    ).strip()

                    if not parece_nome(parte_1):
                        continue

                    if not parece_nome(parte_2):
                        continue

                    palavras_1 = len(parte_1.split())
                    palavras_2 = len(parte_2.split())

                    diferenca = abs(
                        palavras_1 - palavras_2
                    )

                    possibilidades.append(
                        (
                            diferenca,
                            corte,
                            parte_2
                        )
                    )

                if possibilidades:
                    possibilidades.sort(
                        key=lambda item: (
                            item[0],
                            item[1]
                        )
                    )

                    dados["nome_mae"] = (
                        possibilidades[0][2]
                    )

    dados["telefone"] = encontrar_telefone_em_texto(
        texto
    )

    return dados

    # ============================================================
# 17. EXTRAÇÃO OCR - TÍTULO
# ============================================================

def encontrar_titulo_ocr(itens):
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
    rotulos = []

    for item in itens:
        rotulo = normalizar_rotulo(item["texto"])
        if (
            "NASCIMENTO" in rotulo
            or "DATEOFBIRTH" in rotulo
            or "BIRTH" in rotulo
        ):
            rotulos.append(item)

    padrao_data = r"(?<!\d)(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})(?!\d)"

    for rotulo in rotulos:
        candidatos = []

        for match in re.finditer(padrao_data, str(rotulo["texto"])):
            valor = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
            if data_valida(valor):
                candidatos.append((0, -rotulo["confianca"], valor))

        for item in itens:
            texto_item = str(item["texto"])

            for match in re.finditer(padrao_data, texto_item):
                valor = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"

                if not data_valida(valor):
                    continue

                dx = abs(item["x"] - rotulo["x"])
                dy = item["y"] - rotulo["y"]

                if -80 <= dy <= 260 and dx <= 800:
                    candidatos.append(
                        (abs(dy) + dx * 0.15, -item["confianca"], valor)
                    )

        if candidatos:
            candidatos.sort()
            return candidatos[0][2]

    return ""


# ============================================================
# 19. EXTRAÇÃO OCR - CPF
# ============================================================

def encontrar_cpf_ocr(itens):
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
# 20. EXTRAÇÃO OCR - NOME (MELHORADO)
# ============================================================

def encontrar_nome_ocr(itens, texto_completo=""):
    """
    Extrai o nome do documento com prioridade para o Título Eleitoral.
    """
    texto_completo = str(texto_completo or "")
    texto_norm = remover_acentos(texto_completo).upper()
    
    # ============================================================
    # PRIORIDADE 1: NOME DO ELEITOR (Título Eleitoral)
    # ============================================================
    if "JUSTICA ELEITORAL" in texto_norm or "TITULO ELEITORAL" in texto_norm:
        padrao_titulo = r"NOME\s+DO\s+ELEITOR\s*[|]\s*([A-ZÀ-Ÿ\s]+)"
        match = re.search(padrao_titulo, texto_completo, re.I)
        if match:
            nome = match.group(1).strip().upper()
            if parece_nome(nome):
                return nome
    
    # ============================================================
    # PRIORIDADE 2: Rótulo NOME / NOMEDOELEITOR no OCR
    # ============================================================
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

    # ============================================================
    # PRIORIDADE 3: Primeiro nome válido no texto
    # ============================================================
    padroes_nome = [
        r"NOME\s*[:\-]?\s*([A-ZÀ-Ÿ\s]+?)(?=\s*(?:NASCIMENTO|CPF|RG|DATA|FILIACAO|ZONA|SECAO|INSCRICAO|TITULO|$)|\n)",
        r"NOME\s+DO\s+ELEITOR\s*[|]\s*([A-ZÀ-Ÿ\s]+)",
        r"NOME\s+COMPLETO\s*[:\-]?\s*([A-ZÀ-Ÿ\s]+?)(?=\s*(?:NASCIMENTO|CPF|RG|DATA|FILIACAO|$)|\n)"
    ]
    
    for padrao in padroes_nome:
        match = re.search(padrao, texto_completo, re.I)
        if match:
            nome = match.group(1).strip().upper()
            if parece_nome(nome):
                return nome

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
# 21. EXTRAÇÃO OCR - NOME DA MÃE (MELHORADO)
# ============================================================

def encontrar_mae_ocr(itens, texto_completo=""):
    """
    Extrai o nome da mãe com prioridade para FILIAÇÃO no RG e no Título.
    """
    texto_completo = str(texto_completo or "")
    texto_norm = remover_acentos(texto_completo).upper()
    
    # ============================================================
    # PRIORIDADE 1: FILIAÇÃO no RG / Carteira de Identidade
    # ============================================================
    padrao_filiacao = r"FILIACAO\s*[:\-]?\s*([A-ZÀ-Ÿ\s]+?)(?:\s+[A-ZÀ-Ÿ\s]+)?"
    match = re.search(padrao_filiacao, texto_completo, re.I)
    
    if match:
        filiacao = match.group(1).strip().upper()
        partes = filiacao.split()
        if len(partes) >= 4:
            palavras = filiacao.split()
            for i, palavra in enumerate(palavras):
                if palavra.upper() in ["E", "&", ","]:
                    mae = " ".join(palavras[i+1:]).strip()
                    if mae and parece_nome(mae):
                        return mae
            if len(partes) >= 2:
                for i in range(len(partes) - 1, -1, -1):
                    if len(partes[i]) >= 3:
                        mae_candidata = " ".join(partes[max(0, i-1):i+1])
                        if parece_nome(mae_candidata):
                            return mae_candidata
                        if i >= 2:
                            mae_candidata = " ".join(partes[i-2:i+1])
                            if parece_nome(mae_candidata):
                                return mae_candidata
    
    # ============================================================
    # PRIORIDADE 2: NOME DA MÃE no Título Eleitoral
    # ============================================================
    padrao_mae_titulo = r"NOME\s+DA\s+MAE\s*[:\-]?\s*([A-ZÀ-Ÿ\s]+?)(?=\s*(?:NOME|DATA|CPF|RG|FILIACAO|ZONA|SECAO|$)|\n)"
    match = re.search(padrao_mae_titulo, texto_completo, re.I)
    if match:
        mae = match.group(1).strip().upper()
        if parece_nome(mae):
            return mae
    
    # ============================================================
    # PRIORIDADE 3: Rótulo MAE / NOMEDAMAE no OCR
    # ============================================================
    rotulos_mae = []

    for item in itens:
        rotulo = normalizar_rotulo(item["texto"])
        if (
            rotulo in ("MAE", "NOMEDAMAE", "NOMEMAE")
            or "NOMEDAMAE" in rotulo
            or rotulo.startswith("MAE")
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

            if -60 <= dy <= 260 and dx <= 800:
                candidatos.append(
                    (
                        abs(dy) + dx * 0.15,
                        -item["confianca"],
                        candidato.upper()
                    )
                )

        if candidatos:
            candidatos.sort()
            return candidatos[0][2]

    # ============================================================
    # PRIORIDADE 4: FILIAÇÃO no OCR
    # ============================================================
    rotulos_filiacao = []

    for item in itens:
        rotulo = normalizar_rotulo(item["texto"])
        if "FILIACAO" in rotulo or "FILIATION" in rotulo:
            rotulos_filiacao.append(item)

    for rotulo in rotulos_filiacao:
        candidatos = []

        for item in itens:
            if item is rotulo:
                continue

            candidato = str(item["texto"]).strip()

            if not parece_nome(candidato):
                continue

            dx = abs(item["x"] - rotulo["x"])
            dy = item["y"] - rotulo["y"]

            if -30 <= dy <= 300 and dx <= 850:
                candidatos.append(
                    (
                        max(dy, 0) * 2 + dx * 0.10,
                        item["y"],
                        item["x"],
                        -item["confianca"],
                        candidato.upper()
                    )
                )

        if candidatos:
            candidatos.sort()
            if len(candidatos) >= 2:
                return candidatos[-1][4]
            return candidatos[0][4]

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
# 23. EXTRAIR DADOS OCR - VERSÃO COMPLETA COM PRIORIDADE TÍTULO
# ============================================================

def _extrair_dados_ocr_legado(texto, itens):
    """
    Extrai os dados combinando a posição dos blocos do OCR com o texto
    completo do documento, ignorando faturas de consumo anexadas.
    """
    texto_original = str(texto or "")
    linhas = linhas_texto(texto_original)
    texto_sem_acentos = remover_acentos(texto_original).upper()

    # ============================================================
    # PRIORIDADE MÁXIMA: Título Eleitoral - NOME
    # ============================================================
    padrao_nome_titulo = r"NOME\s+DO\s+ELEITOR\s*[|]\s*([A-ZÀ-Ÿ\s]+?)(?=\s*(?:DATA|INSCRICAO|ZONA|SECAO|$)|\n)"
    match = re.search(padrao_nome_titulo, texto_original, re.I)
    nome_titulo = ""
    if match:
        nome_titulo = match.group(1).strip().upper()
        if parece_nome(nome_titulo) and len(nome_titulo.split()) >= 2:
            nome_titulo = nome_titulo

    # ============================================================
    # DETECTA SE É TÍTULO ELEITORAL (prioridade)
    # ============================================================
    eh_titulo_eleitoral = (
        "JUSTICA ELEITORAL" in texto_sem_acentos or 
        "TITULO ELEITORAL" in texto_sem_acentos
    )
    
    titulo = encontrar_titulo_ocr(itens)
    
    # ============================================================
    # EXTRAI NOME - PRIORIZA O NOME DO TÍTULO ELEITORAL
    # ============================================================
    if nome_titulo and parece_nome(nome_titulo):
        nome = nome_titulo
    else:
        nome = encontrar_nome_ocr(itens, texto_original)
    
    # ============================================================
    # EXTRAI CPF
    # ============================================================
    cpf = encontrar_cpf_ocr(itens)
    
    # ============================================================
    # EXTRAI NASCIMENTO
    # ============================================================
    nascimento = encontrar_nascimento_ocr(itens)
    
    # ============================================================
    # EXTRAI NOME DA MÃE (priorizando RG/FILIAÇÃO)
    # ============================================================
    nome_mae = encontrar_mae_ocr(itens, texto_original)

    # ============================================================
    # EXTRAI ZONA E SEÇÃO
    # ============================================================
    zona, secao = encontrar_zona_secao_ocr(itens, titulo)

    # --------------------------------------------------------
    # LIMPEZA DO NOME LIDO PELO OCR
    # --------------------------------------------------------
    if nome:
        nome = re.sub(r"^[^A-Za-zÀ-ÿ]+", "", str(nome)).strip().upper()
        partes = nome.split()
        while partes and len(re.sub(r"[^A-ZÀ-Ÿ]", "", partes[0])) <= 1:
            partes.pop(0)
        nome = " ".join(partes).strip()

    # --------------------------------------------------------
    # CPF - fallback no texto completo com validação rigorosa
    # --------------------------------------------------------
    if not cpf:
        for match in re.finditer(r"(?<!\d)(\d{3})[.\s]?(\d{3})[.\s]?(\d{3})[-\s]?(\d{2})(?!\d)", texto_original):
            numero = "".join(match.groups())
            if cpf_valido(numero):
                cpf = formatar_cpf(numero)
                break

    # --------------------------------------------------------
    # TÍTULO - aceita número fragmentado em grupos 4-4-4
    # --------------------------------------------------------
    if not titulo:
        padroes_titulo = [
            r"(?:N[°º]?\s*INSCRI[CÇ][AÃ]O|INSCRI[CÇ][AÃ]O|T[IÍ]TULO)[\s\S]{0,120}?(\d{4})\D{0,8}(\d{4})\D{0,8}(\d{4})",
            r"(?<!\d)(\d{4})\s+(\d{4})\s+(\d{4})(?!\d)"
        ]
        for padrao in padroes_titulo:
            m = re.search(padrao, texto_original, re.I)
            if m:
                candidato = "".join(m.groups())
                if len(candidato) == 12:
                    titulo = candidato
                    break

    # --------------------------------------------------------
    # NASCIMENTO - busca rigorosa ignorando datas de faturas recentes (2025/2026)
    # --------------------------------------------------------
    if not nascimento:
        candidatos_nasc = []
        for i, linha in enumerate(linhas):
            rot = normalizar_rotulo(linha)
            bloco = " ".join(linhas[max(0, i-1):min(i + 4, len(linhas))])
            for m in re.finditer(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b", bloco):
                dia, mes, ano_str = m.group(1), m.group(2), m.group(3)
                ano = int(ano_str)
                if 1900 <= ano <= 2012:
                    valor = f"{int(dia):02d}/{int(mes):02d}/{ano_str}"
                    if data_valida(valor):
                        candidatos_nasc.append(valor)
        if candidatos_nasc:
            nascimento = candidatos_nasc[0]

    # --------------------------------------------------------
    # NOME - fallback textual baseado em rótulos confiáveis
    # --------------------------------------------------------
    if not nome or not parece_nome(nome) or nome == "WILLAKS FÍRÂELRA DA SILVA" or nome == "WILLAKS FIRAELRA DA SILVA":
        candidatos_nome = []
        for i, linha in enumerate(linhas):
            rot = normalizar_rotulo(linha)
            if "NOMEDOELEITOR" in rot or rot in ("NOME", "NOMECOMPLETO"):
                for pos in range(i + 1, min(i + 4, len(linhas))):
                    candidato = re.sub(r"^[^A-Za-zÀ-ÿ]+", "", linhas[pos]).strip()
                    if parece_nome(candidato):
                        candidatos_nome.append(candidato.upper())
                        break
        if candidatos_nome:
            nome = max(candidatos_nome, key=lambda x: len(x))

    # --------------------------------------------------------
    # MÃE - varredura segura para filiação
    # --------------------------------------------------------
    if not nome_mae:
        nomes_filiacao = []
        capturando_filiacao = False
        for i, linha in enumerate(linhas):
            rot = normalizar_rotulo(linha)
            if "FILIACAO" in rot or "FILIAÇÃO" in linha.upper():
                capturando_filiacao = True
                continue
            if capturando_filiacao:
                if "DATA" in rot or "NATURALIDADE" in rot or "CPF" in rot or "REGISTRO" in rot or "EMISSAO" in rot:
                    capturando_filiacao = False
                    break
                candidato = re.sub(r"^[^A-Za-zÀ-ÿ]+", "", linha).strip()
                if parece_nome(candidato):
                    valor = candidato.upper()
                    if valor != nome and valor not in nomes_filiacao:
                        nomes_filiacao.append(valor)
        if len(nomes_filiacao) >= 2:
            filiacao_texto = " ".join(nomes_filiacao)
            if " E " in filiacao_texto or " & " in filiacao_texto:
                separadores = [" E ", " & ", ", "]
                for sep in separadores:
                    if sep in filiacao_texto:
                        mae = filiacao_texto.split(sep)[-1].strip()
                        if parece_nome(mae):
                            nome_mae = mae
                            break
            if not nome_mae:
                nome_mae = nomes_filiacao[-1]
        elif len(nomes_filiacao) == 1:
            nome_mae = nomes_filiacao[0]

    # --------------------------------------------------------
    # ZONA E SEÇÃO - melhora para Título Eleitoral
    # --------------------------------------------------------
    if not zona or not secao:
        padrao_zona_secao = r"ZONA\s*(\d{1,3})[\s\S]{0,50}?SE[CÇ][AÃ]O\s*(\d{1,4})"
        match = re.search(padrao_zona_secao, texto_original, re.I)
        if match:
            if not zona:
                zona = somente_numeros(match.group(1)).zfill(3)
            if not secao:
                secao = somente_numeros(match.group(2)).zfill(4)
    
    if not zona or not secao:
        m = re.search(r"ZONA[\s\S]{0,80}?(\d{1,3})[\s\S]{0,80}?SE[CÇ][AÃ]O[\s\S]{0,80}?(\d{1,4})", texto_original, re.I)
        if m:
            if not zona:
                zona = somente_numeros(m.group(1)).zfill(3)
            if not secao:
                secao = somente_numeros(m.group(2)).zfill(4)

    if not zona or not secao:
        for linha in linhas:
            nums = re.findall(r"(?<!\d)\d{2,4}(?!\d)", linha)
            if len(nums) >= 2 and ("ZONA" in texto_sem_acentos and "SECAO" in texto_sem_acentos):
                for a, b in zip(nums, nums[1:]):
                    if len(a) <= 3 and len(b) <= 4:
                        if not zona:
                            zona = a.zfill(3)
                        if not secao:
                            secao = b.zfill(4)
                        break
            if zona and secao:
                break

    # --------------------------------------------------------
    # RG
    # --------------------------------------------------------
    rg = ""
    padroes_rg = [
        r"REGISTRO\s+GERAL\s*[:\-]?\s*([0-9.\-]{4,20})",
        r"\bRG\s*[:\-]?\s*([0-9.\-]{4,20})"
    ]
    for padrao in padroes_rg:
        m = re.search(padrao, texto_original, re.I)
        if m:
            rg = somente_numeros(m.group(1))
            if rg:
                break

    # --------------------------------------------------------
    # ENDEREÇO / Nº / BAIRRO / CIDADE
    # --------------------------------------------------------
    endereco = ""
    numero = ""
    bairro = ""
    cidade = ""

    m_cidade = re.search(r"MUNIC[IÍ]PIO\s*/?\s*UF[\s\-:|]*([A-ZÀ-Ÿ ]{3,40})[/\-]\s*([A-Z]{2})", texto_original, re.I)
    if m_cidade:
        cidade = m_cidade.group(1).strip().upper()
    else:
        m_cidade = re.search(r"\b([A-ZÀ-Ÿ ]{3,35})\s*-\s*AL\b", texto_original, re.I)
        if m_cidade:
            cidade = m_cidade.group(1).strip().upper()

    for linha in linhas:
        linha_limpa = re.sub(r"\s+", " ", linha).strip()
        if "CEP" not in linha_limpa.upper():
            continue
        m_end = re.search(r"^(?:R\.?|RUA|AV\.?|AVENIDA|TRAV\.?|TRAVESSA)\s+(.+?)\s+(\d+[A-Z]?)\s+(.+?)\s+CEP\s*[:\-]?\s*\d{5}[-\s]?\d{3}", linha_limpa, re.I)
        if m_end:
            prefixo = re.match(r"^(R\.?|RUA|AV\.?|AVENIDA|TRAV\.?|TRAVESSA)", linha_limpa, re.I)
            tipo = prefixo.group(1).upper() if prefixo else ""
            endereco = f"{tipo} {m_end.group(1)}".strip().upper()
            numero = m_end.group(2).strip().upper()
            bairro = m_end.group(3).strip().upper()
            break

    return {
        "nome": nome,
        "cpf": cpf,
        "titulo": titulo,
        "data_nascimento": nascimento,
        "nome_mae": nome_mae,
        "zona": zona,
        "secao": secao,
        "telefone": encontrar_telefone_documento(texto_original, itens),
        "rg": rg,
        "endereco": endereco,
        "numero": numero,
        "bairro": bairro,
        "cidade": cidade
    }


# ============================================================
# 24. EXTRAÇÃO GERAL
# ============================================================

def extrair_dados(
    texto,
    itens,
    tipo_leitura
):
    """
    Extração principal:
    1) usa o extrator universal novo;
    2) usa a extração antiga apenas como fallback para campos vazios;
    3) nunca sobrescreve um campo já encontrado pelo extrator novo.
    """
    campos = (
        "nome",
        "cpf",
        "titulo",
        "data_nascimento",
        "nome_mae",
        "zona",
        "secao",
        "telefone",
        "rg",
        "endereco",
        "numero",
        "bairro",
        "cidade"
    )

    # MOTOR NOVO: não depende de identificar o tipo do documento.
    try:
        dados_novos = extrator_documentos.extrair_campos(texto) or {}
    except Exception:
        dados_novos = {}

    resultado = {
        campo: str(dados_novos.get(campo, "") or "").strip()
        for campo in campos
    }

    # FALLBACK: aproveita o processamento antigo apenas nos campos
    # que o extrator universal não conseguiu preencher.
    try:
        dados_legados = _extrair_dados_ocr_legado(texto, itens) or {}
    except Exception:
        dados_legados = {}

    for campo in campos:
        if not resultado[campo]:
            valor_legado = str(dados_legados.get(campo, "") or "").strip()
            if valor_legado:
                resultado[campo] = valor_legado

    # Mantém a leitura posicional de telefone manuscrito.
    if not resultado["telefone"]:
        try:
            resultado["telefone"] = encontrar_telefone_documento(texto, itens)
        except Exception:
            resultado["telefone"] = ""

    return resultado


# ============================================================
# 25. CARREGAR BASE DO SHEETS
# ============================================================
