ChatGPT Plus




862d591c-0d97-4596-8bbb-cac449acef54.png
ta dando erro agora 

e73e45d5-4e91-4c76-832a-ff0dbdcef494.png

045b1b4a-a92c-4fe7-b00a-302c4faf0ca5.png

4390a58c-b1c1-4bdf-8c9e-282e15c503bb.png

13898baf-4655-42f6-8388-d4ce1ea4c9c9.png
83cff026-dad2-4d4b-ad93-f2ecbc84ca9d.png
AO MENOS ESSE JPEG NAO LEU

d43cf412-58c5-45b1-922e-78fa2b4d5859.png
EU NEM FIZ AS MUDANÇAS AINDA, FUI ATUALIZAR PRA TESTAR UM PDF E DEU ESSE ERRO AGORA

aaa34926-a093-4948-be86-084f2f8cb9dc.png
TESTO O PDF AGORA?

ac0a5aa3-3ca6-43ed-a24b-f2d9d1cd5efc.png
SALVOU O NOME  NAO

75d3e4ca-d0dc-4c3b-9059-df1ced660738.png
a5c634bf-4bfc-4829-b93b-b9fe72a212e3.png
ACHO QUE O PROBLEMA É PDF MESMO...E OUTRA A SEÇÃO ELE INVENTOU


TITULO.pdf
PDF
E VEJA O PDF QUE SUBI NAO FOI ESCANEADO NAO
FOI O MEU PRA TESTE

Ah, agora sim dá para cravar: esse PDF não é escaneado. E isso muda o diagnóstico.

O arquivo tem texto nativo perfeitamente extraível. Eu consigo ler diretamente dele:

Nome: JAQUELINE MARIA DA SILVA
Nascimento: 28/07/1981
Título: 030111141759
Zona: 055
Seção: 0277
Município: ARAPIRACA / AL 


Então o nosso código cometeu dois erros:

Ele conseguiu extrair o texto nativo, mas nossa função de interpretação escolheu "A AUTENTICIDADE DESTE DOCUMENTO..." como nome.

Pior: estamos carregando o EasyOCR antes de saber se o PDF precisa dele. Mesmo esse PDF tendo texto nativo e não precisando de OCR, o código executa carregar_ocr() antes de começar o lote. Isso explica por que continuamos gastando memória à toa e o app acaba caindo.

Ou seja, para esse PDF, o EasyOCR não deveria sequer ser inicializado.

Como deve ficar
O fluxo correto é:

PDF → tenta texto nativo → achou texto → extrai os campos → acabou.

Só se for:

PDF sem texto → aí sim chama EasyOCR.

E para JPG/PNG:

Imagem → chama EasyOCR.

Isso é muito melhor para lote também. Se você enviar 30 PDFs digitais como esse, nenhum deles precisa carregar o EasyOCR.

Além disso, nesse PDF há uma vantagem enorme: os rótulos e valores estão todos presentes no próprio texto (NOME DO ELEITOR, INSCRIÇÃO, ZONA, SEÇÃO etc.). 

 Portanto, para PDF digital, podemos fazer uma extração específica e muito mais segura em vez daquela heurística que tenta adivinhar o nome.

Então não teste mais essa versão. A próxima correção é justamente tirar o carregamento antecipado do EasyOCR e separar de verdade PDF digital de imagem/PDF escaneado. Isso deve também resolver o nome desse seu PDF.


9a21938c-24ce-4d40-92bb-9eee42af67d3.png
deu certo eu acho
agora se for pdf nao digital? for escaneado? arrumo um pra testar?

7765ea2e-220d-4f95-bb63-1b5fd4a5ed4d.png
deu certo e ate detectou que ja ta cadastrado...agora vou testar um pdf nao digitavel com uma cnh pra ver se ele pega os dados que a tabela exige...ou o codigo nao permite? nome da mãe, data de nascimento etc

6b22daad-3640-455d-a6ec-fb8017bc7116.png
é leu foi nada

98347295-8060-49c1-9ff7-05b64a8adc61.png
676a58fa-e8f4-4dcc-b165-923b136f8301.png

teste1.pdf
PDF
veio nao completo...o nome da mae tb nao puxou completo

Sim — e agora dá para ver exatamente o que aconteceu, porque você mandou o próprio PDF.

O documento tem claramente os dados que precisamos:

Nome: EDILSA KEITE DE AZEVEDO

CPF: 356.682.448-81

Nascimento: 23/12/1985

Filiação: ERNESTO FERREIRA DE AZEVEDO / MARIA LUCIA BELARMINO DE AZEVEDO 


Então a informação existe e está sendo extraída do PDF. O problema agora é nossa lógica, não a qualidade do documento.

Ela está errando três coisas:

1. Nome: pegou CARTEIRA NACIONAL... em vez de EDILSA KEITE DE AZEVEDO.

2. CPF e nascimento: estão na mesma linha do texto extraído (356.682.448-81 23/12/1985), e nossa função atual espera encontrá-los de outra forma. 


3. Nome da mãe: o PDF quebrou o nome em duas linhas:
MARIA LUCIA BELARMINO
DE AZEVEDO
e nosso código guardou apenas a primeira. 


E tem outra coisa importante: não precisamos mandar esse PDF para OCR. A coluna PDF — texto digital está correta neste caso. O PDF possui uma camada textual suficientemente boa; precisamos é melhorar o parser para entender o layout da CNH.

Próxima correção
Não vou mexer no OCR que já acertou o título de eleitor. Vamos alterar somente extrair_dados_pdf_digital() para reconhecer CNH e lidar com campos lado a lado e nomes quebrados em várias linhas.

Com essa CNH específica, o resultado esperado depois da correção será:

EDILSA KEITE DE AZEVEDO | 356.682.448-81 | 23/12/1985 | MARIA LUCIA BELARMINO DE AZEVEDO | ✅ COMPLETO

Título, Zona e Seção ficam vazios, o que está certo para CNH.

Se quiser, já mando só a função completa para substituir, sem reenviar aquelas 700 linhas do app.py.



Texto colado(20260811-161012).txt
Documento

d39170c3-7be6-48e3-91ce-a597f59e02b9.png
nada, mesmo erro


Texto colado(20260811-161507).txt
Documento
mandar esse completo com as alterações?

5379673c-e3de-4233-b4f7-1f533412a0eb.png

teste1(1).pdf
PDF

TITULO(1).pdf
PDF

Texto colado(20260811-171302).txt
Documento
me ajuda so nessa parte que o nome da mae ta saindo tudo e da jaqueline nao sai nome da mae nem a zona secao correta

pode mandar o bloco que precisa substituir...mas com indentação correta, pq quando colo dauqi pra la fica errado

Sim. Pelos dois documentos dá para ver exatamente o erro:

CNH da Edilsa: a filiação está quebrada em várias linhas; o código juntou parte do nome do pai com o da mãe. O correto é MARIA LUCIA BELARMINO DE AZEVEDO. 


Título da Jaqueline: o próprio PDF traz VALDIVIA MARIA DA SILVA e JOSE ANTONIO DA SILVA na filiação, e os dados corretos são Zona 055 / Seção 0277. 


E já achei onde isso está acontecendo no seu código: é dentro de extrair_dados_pdf_digital, principalmente nos blocos 5. ZONA E SEÇÃO e 6. NOME DA MÃE. 


Como você pediu para não correr risco com indentação, em vez de te mandar pedaços soltos para encaixar, vou te passar um único bloco completo, começando em def extrair_dados_pdf_digital(texto): e terminando no return dados. Você apaga essa função inteira e cola a nova no lugar. Assim não tem encaixe no meio de if/for.


c555a2c3-83cc-4fbb-8b28-9c2367706f7b.png
veio incompleto nome da mae da cnh. e jaqueline ok nome da mae mas nao veio zona e seção

257690dc-aaaa-4b7d-9b19-4e2f06fa3cf9.png
nada de zona e seção ainda

4ac41191-a380-41ab-885d-db084c88fb4b.png

app(1).py
Python
sabia, ta dando erro de indentação. por isso odeio seu metodo de colar por cima de bloco

80ed84c8-d1b3-40b5-b07f-1e293a0afd02.png
dc88d2f3-a950-4346-b8d7-c48b67c8134a.png
PQ SERA QUE ESSE NAO PEGOU? 

Dá para ver o motivo pela própria tela. O OCR leu o documento, porque acertou:

Nome: BIANCA STÉFFANIE OLIVEIRA SOUZA ✅

CPF: 112.743.804-21 ✅

O que falhou foi a extração dos outros campos a partir do texto reconhecido, não a leitura da imagem.

Na identidade, os dados estão apresentados de um jeito diferente dos documentos que ajustamos antes:

Nascimento: 14/05/1997

Filiação: BENEIDE CARVALHO OLIVEIRA SOUZA / SEVERINO SALUSTIANO DE SOUZA

O documento usa “Filiação / Filiation”, e a data aparece abaixo de “Data de Nascimento / Date of Birth”.

Nosso extrator genérico ainda não está interpretando corretamente esse layout de RG/CIN. Por isso ele achou nome e CPF, mas deixou nascimento e mãe vazios; consequentemente marcou CONFERIR.

A parte boa é que não precisamos mexer no OCR, porque ele claramente conseguiu ler a imagem. Precisamos ampliar apenas a interpretação do texto para RG/CIN.

E eu não quero voltar a fazer você colar bloco no meio do app.py. 😅 Me manda o app.py atual e eu devolvo o arquivo completo acrescentando suporte a esse tipo de identidade, sem alterar as regras que já acertamos para título e CNH.



Texto colado(20260811-175838).txt
Documento

Pensou por 6s
Recebi o app.py atual. E achei exatamente onde está a limitação: no OCR, a função de mãe só procura rótulos explícitos como MÃE/NOME DA MÃE; ela não trata FILIAÇÃO, que é justamente como essa identidade apresenta os pais. 


Além disso, nascimento já tem uma rotina baseada na posição do rótulo, mas podemos deixá-la compatível com Data de Nascimento / Date of Birth sem prejudicar título e CNH. 


Então agora vou fazer do jeito mais seguro: não mexer em título, zona/seção, salvamento nem no que já está funcionando. Vamos alterar somente a interpretação OCR de RG/CIN.

E como você me mandou o arquivo inteiro justamente para evitar a novela de indentação, não vou mandar bloco para você encaixar no meio. Vou preparar o app.py completo já alterado para você substituir o atual.


MANDA

Pensou por 28s
Pronto. Peguei o seu app.py inteiro, alterei somente a leitura OCR para melhorar:

Data de nascimento em RG/CIN;

Filiação / Filiação-Filiation para capturar o nome da mãe;

sem lista de nomes;

sem mexer no que já estava funcionando para título eleitoral;

arquivo validado sem erro de sintaxe/indentação.

No seu código anterior, a mãe via OCR só era procurada quando existia literalmente MÃE/NOME DA MÃE, por isso essa nova identidade com o campo Filiação / Filiation ficava vazia. 


Substitua o app.py inteiro por este:

📥 Baixar app_corrigido.py

Depois renomeie para app.py, envie ao GitHub e teste essa mesma identidade primeiro.


app_corrigido.py
Código


Biblioteca
/
app_corrigido.py


import streamlit as st
import requests
import re
import io
import gc
import unicodedata
import numpy as np
import pandas as pd
from PIL import Image, ImageOps
import fitz
import sheets

# ============================================================
# 1. CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Sistema de Cadastro CP",
    layout="wide",
    page_icon="📋"
)


# ============================================================
# 2. CSS
# ============================================================

st.markdown(
    """
    <style>
    .stApp {
        background-color: #eef2f5 !important;
    }

    div.stButton > button {
        background-color: #0056b3 !important;
        color: white !important;
        border-radius: 12px !important;
        border: 2px solid #0056b3 !important;
        font-weight: bold !important;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# 3. WEBHOOK
# ============================================================

try:
    WEBHOOK_URL = st.secrets["WEBHOOK_URL"]

except Exception:
    st.error(
        "Erro nas chaves de segurança (Secrets) do Streamlit."
    )
    st.stop()


# ============================================================
# 4. FUNÇÕES BÁSICAS
# ============================================================

def somente_numeros(valor):
    return re.sub(
        r"\D",
        "",
        str(valor or "")
    )


def normalizar_texto(valor):
    return str(
        valor or ""
    ).strip().upper()


def remover_acentos(valor):
    valor = str(
        valor or ""
    )

    return "".join(
        caractere
        for caractere in unicodedata.normalize(
            "NFD",
            valor
        )
        if unicodedata.category(
            caractere
        ) != "Mn"
    )


def normalizar_rotulo(valor):
    valor = remover_acentos(
        valor
    ).upper()

    return re.sub(
        r"[^A-Z0-9]",
        "",
        valor
    )


def formatar_cpf(cpf):
    cpf = somente_numeros(
        cpf
    )

    if len(cpf) != 11:
        return cpf

    return (
        f"{cpf[0:3]}."
        f"{cpf[3:6]}."
        f"{cpf[6:9]}-"
        f"{cpf[9:11]}"
    )


def cpf_valido(cpf):
    """Valida CPF pelos dígitos verificadores. Não infere nem corrige números."""
    cpf = somente_numeros(cpf)

    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    for tamanho in (9, 10):
        soma = sum(
            int(cpf[i]) * (tamanho + 1 - i)
            for i in range(tamanho)
        )
        digito = (soma * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(cpf[tamanho]):
            return False

    return True


def data_valida(valor):
    """Valida uma data real no formato DD/MM/AAAA, DD-MM-AAAA ou DD.MM.AAAA."""
    from datetime import datetime

    valor = str(valor or "").strip()
    match = re.fullmatch(r"(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})", valor)

    if not match:
        return False

    try:
        datetime.strptime(
            f"{match.group(1)}/{match.group(2)}/{match.group(3)}",
            "%d/%m/%Y"
        )
        return 1900 <= int(match.group(3)) <= datetime.now().year
    except ValueError:
        return False


# ============================================================
# 5. OCR
# SÓ CARREGA SE REALMENTE PRECISAR
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
# 7. OCR DE IMAGEM
# ============================================================

def executar_ocr_imagem(imagem):
    leitor = carregar_ocr()

    imagem = preparar_imagem(
        imagem
    )

    imagem_np = np.array(
        imagem
    )

    resultado = leitor.readtext(
        imagem_np,
        detail=1,
        paragraph=False,
        decoder="greedy"
    )

    itens = []

    for item in resultado:
        try:
            caixa = item[0]

            texto = str(
                item[1]
            ).strip()

            confianca = float(
                item[2]
            )

            if not texto:
                continue

            xs = [
                ponto[0]
                for ponto in caixa
            ]

            ys = [
                ponto[1]
                for ponto in caixa
            ]

            itens.append(
                {
                    "texto": texto,
                    "confianca": confianca,
                    "x": sum(xs) / len(xs),
                    "y": sum(ys) / len(ys)
                }
            )

        except Exception:
            continue

    itens.sort(
        key=lambda item: (
            round(
                item["y"] / 20
            ),
            item["x"]
        )
    )

    texto = "\n".join(
        item["texto"]
        for item in itens
    )

    del imagem_np

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
    nome = arquivo.name.lower()

    if nome.endswith(
        ".pdf"
    ):
        texto_nativo = extrair_texto_pdf(
            arquivo
        )

        if pdf_tem_texto_util(
            texto_nativo
        ):
            return (
                texto_nativo,
                [],
                "PDF — texto digital"
            )

        texto, itens = executar_ocr_pdf(
            arquivo
        )

        return (
            texto,
            itens,
            "PDF — OCR"
        )

    arquivo.seek(0)

    imagem = Image.open(
        arquivo
    )

    texto, itens = executar_ocr_imagem(
        imagem
    )

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
        "secao": ""
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

    if not dados["data_nascimento"]:
        for linha in linhas:
            match = re.search(
                r"\b(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})\b",
                linha
            )

            if match:
                valor = (
                    f"{match.group(1)}/"
                    f"{match.group(2)}/"
                    f"{match.group(3)}"
                )

                if data_valida(valor):
                    dados["data_nascimento"] = valor
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

        # A data pode ter sido reconhecida no mesmo bloco do rótulo.
        for match in re.finditer(padrao_data, str(rotulo["texto"])):
            valor = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
            if data_valida(valor):
                candidatos.append((0, -rotulo["confianca"], valor))

        # Ou em um bloco próximo, normalmente abaixo ou ao lado do rótulo.
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

    # Fallback conservador: se só houver uma data válida no documento,
    # ela pode ser usada como nascimento. Com várias datas, não adivinha.
    datas = []

    for item in itens:
        for match in re.finditer(padrao_data, str(item["texto"])):
            valor = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
            if data_valida(valor) and valor not in datas:
                datas.append(valor)

    if len(datas) == 1:
        return datas[0]

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
# 20. EXTRAÇÃO OCR - NOME
# ============================================================

def encontrar_nome_ocr(itens):
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
    # 1. Prioridade máxima: documento que identifica explicitamente a mãe.
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

    # 2. RG/CIN e outros documentos podem trazer apenas FILIAÇÃO/FILIATION.
    # Nesses documentos, captura o primeiro nome completo associado ao campo,
    # sem usar lista de nomes próprios nem inventar conteúdo.
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

            # Campo de filiação costuma ficar imediatamente abaixo do rótulo.
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
# 23. EXTRAIR DADOS OCR
# ============================================================

def extrair_dados_ocr(
    texto,
    itens
):
    titulo = encontrar_titulo_ocr(
        itens
    )

    nome = encontrar_nome_ocr(
        itens
    )

    cpf = encontrar_cpf_ocr(
        itens
    )

    nascimento = encontrar_nascimento_ocr(
        itens
    )

    nome_mae = encontrar_mae_ocr(
        itens
    )

    zona, secao = encontrar_zona_secao_ocr(
        itens,
        titulo
    )

    return {
        "nome": nome,
        "cpf": cpf,
        "titulo": titulo,
        "data_nascimento": nascimento,
        "nome_mae": nome_mae,
        "zona": zona,
        "secao": secao
    }


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


# ============================================================
# 25. CARREGAR BASE DO SHEETS
# ============================================================

@st.cache_data(ttl=60)
def carregar_base():
    try:
        resposta = requests.get(
            WEBHOOK_URL,
            timeout=10
        )

        if resposta.status_code != 200:
            return []

        dados = resposta.json()

        if isinstance(
            dados,
            list
        ):
            return dados

    except Exception:
        pass

    return []


# ============================================================
# 26. VERIFICAR DUPLICIDADE
# ============================================================

def verificar_duplicidade(
    dados,
    base
):
    titulo_novo = somente_numeros(
        dados.get(
            "titulo",
            ""
        )
    )

    cpf_novo = somente_numeros(
        dados.get(
            "cpf",
            ""
        )
    )

    for pessoa in base:
        titulo_existente = somente_numeros(
            pessoa.get(
                "titulo",
                ""
            )
        )

        cpf_existente = somente_numeros(
            pessoa.get(
                "cpf",
                ""
            )
        )

        if (
            titulo_novo
            and titulo_existente
            and titulo_novo.lstrip("0")
            == titulo_existente.lstrip("0")
        ):
            return True, pessoa

        if (
            cpf_novo
            and cpf_existente
            and cpf_novo
            == cpf_existente
        ):
            return True, pessoa

    return False, None


# ============================================================
# 27. REGRA DE DADOS MÍNIMOS
# ============================================================

def verificar_dados_minimos(
    dados
):
    faltando = []

    if not dados.get(
        "nome"
    ):
        faltando.append(
            "nome"
        )

    if not dados.get(
        "data_nascimento"
    ):
        faltando.append(
            "nascimento"
        )

    if not dados.get(
        "nome_mae"
    ):
        faltando.append(
            "nome da mãe"
        )

    if (
        not dados.get("cpf")
        and not dados.get("titulo")
    ):
        faltando.append(
            "CPF ou título"
        )

    return faltando


# ============================================================
# 28. CLASSIFICAÇÃO
# ============================================================

def classificar_resultado(
    dados,
    duplicado
):
    if duplicado:
        return "⚠️ JÁ CADASTRADO"

    faltando = verificar_dados_minimos(
        dados
    )

    if faltando:
        return (
            "❌ FALTA: "
            + ", ".join(
                faltando
            ).upper()
        )

    return "✅ COMPLETO"


# ============================================================
# 29. SUPERVISORES
# ============================================================

def obter_supervisores(
    base
):
    supervisores = []

    subs = [
        "SEM SUBSUPERVISOR"
    ]

    for item in base:
        sup = str(
            item.get(
                "supervisor",
                ""
            )
        ).strip().upper()

        sub = str(
            item.get(
                "subsupervisor",
                ""
            )
        ).strip().upper()

        if (
            sup
            and sup not in supervisores
        ):
            supervisores.append(
                sup
            )

        if (
            sub
            and sub not in subs
        ):
            subs.append(
                sub
            )

    return (
        sorted(
            supervisores
        ),
        sorted(
            subs
        )
    )


# ============================================================
# 30. CABEÇALHO
# ============================================================

st.title(
    "📋 Sistema de Cadastro CP"
)

st.caption(
    "Leitura e conferência de documentos"
)

st.markdown(
    "---"
)


# ============================================================
# 31. CARREGAR BASE
# ============================================================

base = carregar_base()

lista_sup, lista_sub = obter_supervisores(
    base
)


# ============================================================
# 32. SIDEBAR
# ============================================================

with st.sidebar:
    st.header(
        "⚙️ Configuração"
    )

    sup_opcao = st.selectbox(
        "Supervisor",
        lista_sup
        + [
            "➕ Cadastrar Novo Supervisor"
        ]
    )

    if (
        sup_opcao
        == "➕ Cadastrar Novo Supervisor"
    ):
        supervisor = st.text_input(
            "Novo Supervisor"
        ).upper()

    else:
        supervisor = sup_opcao

    sub_opcao = st.selectbox(
        "Subsupervisor",
        lista_sub
        + [
            "➕ Cadastrar Novo Sub"
        ]
    )

    if (
        sub_opcao
        == "➕ Cadastrar Novo Sub"
    ):
        sub = st.text_input(
            "Novo Sub"
        ).upper()

    else:
        sub = sub_opcao

    st.markdown(
        "---"
    )

    menu = st.radio(
        "Escolha a Operação:",
        [
            "📸 Envio de Documentos",
            "✍️ Formulário Manual"
        ]
    )


# ============================================================
# 33. ENVIO DE DOCUMENTOS
# ============================================================

if menu == "📸 Envio de Documentos":

    st.subheader(
        "📁 Processamento de Documentos"
    )

    st.caption(
        f"Supervisor: {supervisor} | "
        f"Subsupervisor: {sub}"
    )

    arquivos = st.file_uploader(
        "Selecione fotos ou PDFs",
        accept_multiple_files=True,
        type=[
            "pdf",
            "jpg",
            "jpeg",
            "png"
        ]
    )

    if arquivos:
        st.info(
            f"{len(arquivos)} arquivo(s) selecionado(s). "
            "Cada documento será processado individualmente."
        )

        if st.button(
            "🔎 Processar Lote"
        ):
            resultados = []

            total = len(
                arquivos
            )

            barra = st.progress(
                0
            )

            status_area = st.empty()

            for indice, arquivo in enumerate(
                arquivos
            ):
                status_area.info(
                    f"Processando "
                    f"{indice + 1} de {total}: "
                    f"{arquivo.name}"
                )

                try:
                    texto, itens, tipo = ler_documento(
                        arquivo
                    )

                    dados = extrair_dados(
                        texto,
                        itens,
                        tipo
                    )

                    duplicado, existente = verificar_duplicidade(
                        dados,
                        base
                    )

                    resultado = classificar_resultado(
                        dados,
                        duplicado
                    )

                    existente_nome = ""
                    existente_sup = ""

                    if duplicado and existente:
                        existente_nome = str(
                            existente.get(
                                "nome",
                                ""
                            )
                        )

                        existente_sup = str(
                            existente.get(
                                "supervisor",
                                ""
                            )
                        )

                    resultados.append(
                        {
                            "Arquivo":
                                arquivo.name,

                            "Nome":
                                dados["nome"],

                            "CPF":
                                dados["cpf"],

                            "Título":
                                dados["titulo"],

                            "Nascimento":
                                dados[
                                    "data_nascimento"
                                ],

                            "Nome da mãe":
                                dados[
                                    "nome_mae"
                                ],

                            "Zona":
                                dados["zona"],

                            "Seção":
                                dados["secao"],

                            "Leitura":
                                tipo,

                            "Resultado":
                                resultado,

                            "Já cadastrado como":
                                existente_nome,

                            "Supervisor atual":
                                existente_sup,

                            "_dados":
                                dados.copy()
                        }
                    )

                    del texto
                    del itens

                    gc.collect()

                except Exception as erro:
                    resultados.append(
                        {
                            "Arquivo":
                                arquivo.name,

                            "Nome":
                                "",

                            "CPF":
                                "",

                            "Título":
                                "",

                            "Nascimento":
                                "",

                            "Nome da mãe":
                                "",

                            "Zona":
                                "",

                            "Seção":
                                "",

                            "Leitura":
                                "",

                            "Resultado":
                                "❌ ERRO",

                            "Já cadastrado como":
                                "",

                            "Supervisor atual":
                                ""
                        }
                    )

                    st.error(
                        f"Erro em "
                        f"{arquivo.name}: "
                        f"{erro}"
                    )

                barra.progress(
                    (
                        indice + 1
                    )
                    / total
                )

                gc.collect()

            status_area.success(
                "Processamento concluído."
            )

            st.session_state[
                "resultado_lote"
            ] = resultados


    # ========================================================
    # RESULTADOS
    # ========================================================

    if (
        "resultado_lote"
        in st.session_state
    ):
        resultados = st.session_state[
            "resultado_lote"
        ]

        if resultados:
            st.markdown(
                "---"
            )

            st.subheader(
                "📊 Resultado do Lote"
            )

            completos = sum(
                1
                for r in resultados
                if r["Resultado"]
                == "✅ COMPLETO"
            )

            duplicados = sum(
                1
                for r in resultados
                if r["Resultado"]
                == "⚠️ JÁ CADASTRADO"
            )

            conferir = (
                len(resultados)
                - completos
                - duplicados
            )

            col1, col2, col3 = st.columns(
                3
            )

            col1.metric(
                "Completos",
                completos
            )

            col2.metric(
                "Já cadastrados",
                duplicados
            )

            col3.metric(
                "Conferir",
                conferir
            )

            resultados_visiveis = []

            for item in resultados:
                item_visivel = {
                    chave: valor
                    for chave, valor in item.items()
                    if chave != "_dados"
                }

                resultados_visiveis.append(
                    item_visivel
                )

            df_resultados = pd.DataFrame(
                resultados_visiveis
            )

            st.dataframe(
                df_resultados,
                use_container_width=True,
                hide_index=True
            )

            # ====================================================
            # SALVAR CADASTROS COMPLETOS NA TABELA
            # ====================================================

            aptos_para_salvar = [
                item
                for item in resultados
                if (
                    item.get("Resultado") == "✅ COMPLETO"
                    and item.get("_dados")
                )
            ]

            if aptos_para_salvar:

                st.markdown("---")

                st.info(
                    f"📥 {len(aptos_para_salvar)} cadastro(s) "
                    f"completo(s) pronto(s) para salvar."
                )

                if st.button(
                    "💾 Salvar completos na TABELA",
                    type="primary"
                ):
                    salvos = 0
                    duplicados_salvar = 0
                    erros_salvar = 0

                    progresso_salvar = st.progress(0)

                    for indice_salvar, item in enumerate(
                        aptos_para_salvar
                    ):
                        dados_salvar = item["_dados"]

                        retorno = sheets.salvar_cadastro(
                            WEBHOOK_URL,
                            dados_salvar,
                            supervisor,
                            sub,
                            dados_base=base
                        )

                        status_salvar = retorno.get(
                            "status",
                            "ERRO"
                        )

                        if status_salvar == "SUCESSO":
                            salvos += 1

                        elif status_salvar == "DUPLICADO":
                            duplicados_salvar += 1

                        else:
                            erros_salvar += 1

                            st.error(
                                f"{item['Arquivo']}: "
                                f"{retorno.get('mensagem', 'Erro ao salvar.')}"
                            )

                        progresso_salvar.progress(
                            (indice_salvar + 1)
                            / len(aptos_para_salvar)
                        )

                    st.success(
                        f"Salvamento concluído: "
                        f"{salvos} salvo(s), "
                        f"{duplicados_salvar} duplicado(s) "
                        f"e {erros_salvar} erro(s)."
                    )

                    st.cache_data.clear()

            st.caption(
                "ℹ️ Para ser considerado completo: "
                "Nome + Nascimento + Nome da mãe + "
                "CPF ou Título. "
                "Nenhum cadastro do lote foi gravado "
                "automaticamente."
            )


# ============================================================
# 34. FORMULÁRIO MANUAL
# ============================================================

elif menu == "✍️ Formulário Manual":

    st.subheader(
        "✍️ Consulta & Cadastro Manual"
    )

    if (
        "busca_realizada"
        not in st.session_state
    ):
        st.session_state.update(
            {
                "busca_realizada":
                    False,

                "titulo":
                    "",

                "encontrado":
                    None
            }
        )

    titulo_input = st.text_input(
        "Título de Eleitor:",
        value=st.session_state.titulo
    )

    if st.button(
        "🔍 Pesquisar"
    ):
        st.session_state.titulo = (
            titulo_input
        )

        titulo_pesquisado = somente_numeros(
            titulo_input
        ).lstrip(
            "0"
        )

        encontrado = None

        for pessoa in base:
            titulo_base = somente_numeros(
                pessoa.get(
                    "titulo",
                    ""
                )
            ).lstrip(
                "0"
            )

            if (
                titulo_pesquisado
                and titulo_base
                == titulo_pesquisado
            ):
                encontrado = pessoa
                break

        st.session_state.encontrado = (
            encontrado
        )

        st.session_state.busca_realizada = (
            True
        )

    if st.session_state.busca_realizada:

        if st.session_state.encontrado:
            e = st.session_state.encontrado

            st.error(
                f"⚠️ Já cadastrado: "
                f"{e.get('nome')} | "
                f"Supervisor: "
                f"{e.get('supervisor')}"
            )

            if st.button(
                "Limpar"
            ):
                st.session_state.busca_realizada = (
                    False
                )

                st.session_state.encontrado = (
                    None
                )

                st.session_state.titulo = ""

                st.rerun()

        else:
            st.success(
                "Título não localizado na base. "
                "O cadastro pode ser realizado."
            )

            with st.form(
                "cadastro_manual"
            ):
                nome = st.text_input(
                    "Nome *"
                )

                cpf = st.text_input(
                    "CPF"
                )

                data_nasc = st.text_input(
                    "Data de Nascimento "
                    "(DD/MM/AAAA)"
                )

                nome_mae = st.text_input(
                    "Nome da mãe"
                )

                salvar = st.form_submit_button(
                    "💾 Salvar"
                )

                if salvar:
                    if not nome:
                        st.error(
                            "Informe o nome."
                        )

                    else:
                        payload = {
                            "titulo":
                                st.session_state.titulo,

                            "nome":
                                nome,

                            "cpf":
                                cpf,

                            "data_nascimento":
                                data_nasc,

                            "nome_mae":
                                nome_mae,

                            "supervisor":
                                supervisor,

                            "subsupervisor":
                                sub
                        }

                        try:
                            resposta = requests.post(
                                WEBHOOK_URL,
                                json=payload,
                                timeout=30
                            )

                            resultado = resposta.json()

                            if (
                                resultado.get(
                                    "status"
                                )
                                == "SUCESSO"
                            ):
                                st.success(
                                    "Salvo com sucesso!"
                                )

                                st.cache_data.clear()

                                st.session_state.busca_realizada = (
                                    False
                                )

                                st.session_state.encontrado = (
                                    None
                                )

                                st.session_state.titulo = ""

                                st.rerun()

                            else:
                                st.error(
                                    resultado.get(
                                        "mensagem",
                                        "Erro ao salvar."
                                    )
                                )

                        except Exception as erro:
                            st.error(
                                f"Erro ao salvar: {erro}"
                            )
