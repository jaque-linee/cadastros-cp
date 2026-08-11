import streamlit as st
import requests
import re
import io
import gc
import numpy as np
import pandas as pd
from PIL import Image, ImageOps
import fitz


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

    return (
        str(valor or "")
        .strip()
        .upper()
    )


def formatar_cpf(cpf):

    cpf = somente_numeros(cpf)

    if len(cpf) != 11:
        return cpf

    return (
        f"{cpf[0:3]}."
        f"{cpf[3:6]}."
        f"{cpf[6:9]}-"
        f"{cpf[9:11]}"
    )


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

    imagem = imagem.convert("RGB")

    largura, altura = imagem.size


    # --------------------------------------------
    # AUMENTA IMAGENS MUITO PEQUENAS
    # --------------------------------------------

    if largura < 1200:

        proporcao = 1200 / largura

        imagem = imagem.resize(
            (
                1200,
                int(altura * proporcao)
            ),
            Image.Resampling.LANCZOS
        )


    # --------------------------------------------
    # REDUZ IMAGENS GIGANTES
    # --------------------------------------------

    if imagem.width > 2000:

        proporcao = 2000 / imagem.width

        imagem = imagem.resize(
            (
                2000,
                int(imagem.height * proporcao)
            ),
            Image.Resampling.LANCZOS
        )


    return imagem


# ============================================================
# 7. OCR DE UMA IMAGEM
# ============================================================

def executar_ocr_imagem(
    imagem,
    leitor
):

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
            item["y"],
            item["x"]
        )
    )


    texto = "\n".join(
        item["texto"]
        for item in itens
    )


    # Libera array pesado
    del imagem_np

    gc.collect()


    return texto, itens


# ============================================================
# 8. EXTRAIR TEXTO NATIVO DO PDF
# ============================================================

def extrair_texto_pdf(
    arquivo
):

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
# 9. TRANSFORMAR UMA PÁGINA PDF EM IMAGEM
# ============================================================

def pagina_pdf_para_imagem(
    pagina
):

    # Resolução controlada para não explodir memória
    pix = pagina.get_pixmap(
        matrix=fitz.Matrix(1.5, 1.5),
        alpha=False
    )


    imagem = Image.open(
        io.BytesIO(
            pix.tobytes("jpeg")
        )
    ).convert("RGB")


    del pix

    gc.collect()


    return imagem


# ============================================================
# 10. OCR DE PDF ESCANEADO
# ============================================================

def executar_ocr_pdf(
    arquivo,
    leitor
):

    bytes_pdf = arquivo.getvalue()

    documento = fitz.open(
        stream=bytes_pdf,
        filetype="pdf"
    )


    textos = []

    todos_itens = []


    # Processa UMA página de cada vez
    for numero_pagina in range(
        len(documento)
    ):

        pagina = documento[
            numero_pagina
        ]

        imagem = pagina_pdf_para_imagem(
            pagina
        )


        texto, itens = (
            executar_ocr_imagem(
                imagem,
                leitor
            )
        )


        if texto:

            textos.append(
                texto
            )


        todos_itens.extend(
            itens
        )


        # Libera página imediatamente
        del imagem

        gc.collect()


    documento.close()


    return (
        "\n".join(textos),
        todos_itens
    )


# ============================================================
# 11. CONVERTER TEXTO NATIVO EM ITENS
# ============================================================

def texto_para_itens(
    texto
):

    itens = []

    linhas = [
        linha.strip()
        for linha in texto.splitlines()
        if linha.strip()
    ]


    for indice, linha in enumerate(
        linhas
    ):

        itens.append(
            {
                "texto": linha,
                "confianca": 1.0,
                "x": 0,
                "y": indice * 30
            }
        )


    return itens


# ============================================================
# 12. LER UM DOCUMENTO
# ============================================================

def ler_documento(
    arquivo,
    leitor
):

    nome = arquivo.name.lower()


    # ========================================================
    # PDF
    # ========================================================

    if nome.endswith(
        ".pdf"
    ):

        # Primeiro tenta texto real do PDF
        texto_nativo = (
            extrair_texto_pdf(
                arquivo
            )
        )


        # Se houver quantidade razoável de texto,
        # não usa OCR.
        if len(
            re.sub(
                r"\s",
                "",
                texto_nativo
            )
        ) >= 30:

            itens = texto_para_itens(
                texto_nativo
            )

            return (
                texto_nativo,
                itens,
                "PDF — texto digital"
            )


        # PDF escaneado
        texto, itens = (
            executar_ocr_pdf(
                arquivo,
                leitor
            )
        )


        return (
            texto,
            itens,
            "PDF — OCR"
        )


    # ========================================================
    # JPG / PNG
    # ========================================================

    arquivo.seek(0)

    imagem = Image.open(
        arquivo
    )


    texto, itens = (
        executar_ocr_imagem(
            imagem,
            leitor
        )
    )


    del imagem

    gc.collect()


    return (
        texto,
        itens,
        "Imagem — OCR"
    )


# ============================================================
# 13. ENCONTRAR TÍTULO
# ============================================================

def encontrar_titulo(
    itens
):

    candidatos = []


    for item in itens:

        numeros = somente_numeros(
            item["texto"]
        )


        if len(numeros) == 12:

            candidatos.append(
                (
                    item["confianca"],
                    numeros
                )
            )


    if candidatos:

        candidatos.sort(
            reverse=True
        )

        return candidatos[
            0
        ][1]


    return ""


# ============================================================
# 14. ENCONTRAR NASCIMENTO
# ============================================================

def encontrar_nascimento(
    itens
):

    datas = []


    for item in itens:

        texto = item["texto"]


        for match in re.finditer(
            r"\b"
            r"(\d{2})"
            r"[\/.\-]"
            r"(\d{2})"
            r"[\/.\-]"
            r"(\d{4})"
            r"\b",
            texto
        ):

            dia = match.group(1)

            mes = match.group(2)

            ano = match.group(3)


            try:

                dia_int = int(dia)

                mes_int = int(mes)

                ano_int = int(ano)


                if (
                    1 <= dia_int <= 31
                    and 1 <= mes_int <= 12
                    and 1900 <= ano_int <= 2026
                ):

                    datas.append(
                        (
                            item["y"],
                            f"{dia}/{mes}/{ano}"
                        )
                    )

            except Exception:
                pass


    if datas:

        datas.sort()

        return datas[
            0
        ][1]


    return ""


# ============================================================
# 15. ENCONTRAR CPF
# ============================================================

def encontrar_cpf(
    itens
):

    # Primeiro procura linha explicitamente associada a CPF
    for indice, item in enumerate(
        itens
    ):

        texto = normalizar_texto(
            item["texto"]
        )


        if "CPF" in texto:

            numeros = somente_numeros(
                texto
            )


            if len(numeros) == 11:

                return formatar_cpf(
                    numeros
                )


            # Tenta próxima linha
            if indice + 1 < len(
                itens
            ):

                numeros = somente_numeros(
                    itens[
                        indice + 1
                    ]["texto"]
                )

                if len(numeros) == 11:

                    return formatar_cpf(
                        numeros
                    )


    # Segunda tentativa
    for item in itens:

        numeros = somente_numeros(
            item["texto"]
        )


        if len(numeros) == 11:

            return formatar_cpf(
                numeros
            )


    return ""


# ============================================================
# 16. VERIFICAR SE TEXTO PARECE NOME
# ============================================================

def parece_nome(
    texto
):

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


    texto_upper = (
        texto.upper()
    )


    ignorar = [

        "REPÚBLICA",
        "REPUBLICA",
        "FEDERATIVA",
        "BRASIL",
        "JUSTIÇA",
        "JUSTICA",
        "ELEITORAL",
        "TÍTULO",
        "TITULO",
        "IDENTIFICAÇÃO",
        "IDENTIFICACAO",
        "BIOMETRICA",
        "BIOMÉTRICA",
        "NOME DO ELEITOR",
        "NOMEDOELEITOR",
        "DATA DE NASCIMENTO",
        "NASCIMENTO",
        "INSCRIÇÃO",
        "INSCRICAO",
        "CPF",
        "RG",
        "ZONA",
        "SEÇÃO",
        "SECAO",
        "MUNICIPIO",
        "MUNICÍPIO",
        "EMISSÃO",
        "EMISSAO",
        "VALIDO SOMENTE",
        "VÁLIDO SOMENTE",
        "MARCA D'AGUA",
        "MARCA D'ÁGUA",
        "SECRETARIA",
        "ESTADO",
        "CARTEIRA",
        "IDENTIDADE"
    ]


    for termo in ignorar:

        if termo in texto_upper:

            return False


    palavras = texto.split()


    if not (
        2 <= len(
            palavras
        ) <= 8
    ):

        return False


    letras = re.sub(
        r"[^A-Za-zÀ-ÿ]",
        "",
        texto
    )


    if len(
        letras
    ) < 8:

        return False


    return True


# ============================================================
# 17. ENCONTRAR NOME
# ============================================================

def encontrar_nome(
    itens
):

    # --------------------------------------------------------
    # Procura rótulo NOME
    # --------------------------------------------------------

    for indice, item in enumerate(
        itens
    ):

        texto = normalizar_texto(
            item["texto"]
        )


        texto_limpo = re.sub(
            r"[^A-ZÀ-Ú]",
            "",
            texto
        )


        if (
            "NOMEDOELEITOR"
            in texto_limpo
            or texto_limpo
            == "NOME"
        ):

            for proximo in itens[
                indice + 1:
                indice + 6
            ]:

                candidato = (
                    proximo[
                        "texto"
                    ]
                )


                if parece_nome(
                    candidato
                ):

                    return (
                        candidato
                        .strip()
                        .upper()
                    )


    # --------------------------------------------------------
    # Melhor candidato geral
    # --------------------------------------------------------

    candidatos = []


    for item in itens:

        candidato = (
            item[
                "texto"
            ].strip()
        )


        if parece_nome(
            candidato
        ):

            quantidade = len(
                candidato.split()
            )


            pontuacao = (
                quantidade * 20
                + len(candidato)
                + (
                    item[
                        "confianca"
                    ] * 10
                )
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

        return candidatos[
            0
        ][1]


    return ""


# ============================================================
# 18. ENCONTRAR ZONA E SEÇÃO
# ============================================================

def encontrar_zona_secao(
    itens,
    titulo
):

    zona = ""

    secao = ""


    item_zona = None

    item_secao = None


    # --------------------------------------------------------
    # LOCALIZA OS RÓTULOS
    # --------------------------------------------------------

    for item in itens:

        texto = normalizar_texto(
            item["texto"]
        )


        texto_limpo = re.sub(
            r"[^A-ZÀ-Ú]",
            "",
            texto
        )


        if texto_limpo == "ZONA":

            item_zona = item


        if texto_limpo in [
            "SECAO",
            "SEÇÃO"
        ]:

            item_secao = item


    # --------------------------------------------------------
    # FUNÇÃO PARA ACHAR VALOR ABAIXO DO RÓTULO
    # --------------------------------------------------------

    def numero_proximo(
        rotulo,
        max_digitos
    ):

        if not rotulo:
            return ""


        candidatos = []


        for item in itens:

            if item is rotulo:
                continue


            numero = somente_numeros(
                item["texto"]
            )


            if not numero:
                continue


            if numero == titulo:
                continue


            if not (
                1 <= len(
                    numero
                ) <= max_digitos
            ):

                continue


            # Deve estar abaixo
            if (
                item["y"]
                <= rotulo["y"]
            ):

                continue


            distancia_y = (
                item["y"]
                - rotulo["y"]
            )


            distancia_x = abs(
                item["x"]
                - rotulo["x"]
            )


            # Damos muito mais peso
            # à distância horizontal
            pontuacao = (
                distancia_y
                + (
                    distancia_x
                    * 3
                )
            )


            if distancia_y <= 300:

                candidatos.append(
                    (
                        pontuacao,
                        numero
                    )
                )


        if candidatos:

            candidatos.sort()

            return candidatos[
                0
            ][1]


        return ""


    zona = numero_proximo(
        item_zona,
        3
    )


    secao = numero_proximo(
        item_secao,
        4
    )


    # --------------------------------------------------------
    # FALLBACK ESPECÍFICO PARA TÍTULO ELEITORAL
    # --------------------------------------------------------

    if (
        not zona
        or not secao
    ):

        item_titulo = None


        for item in itens:

            if (
                somente_numeros(
                    item["texto"]
                )
                == titulo
            ):

                item_titulo = item

                break


        if item_titulo:

            numeros = []


            for item in itens:

                numero = somente_numeros(
                    item["texto"]
                )


                if not numero:
                    continue


                if numero == titulo:
                    continue


                # Somente itens aproximadamente
                # na mesma linha do título ou logo abaixo
                distancia_y = abs(
                    item["y"]
                    - item_titulo["y"]
                )


                if distancia_y > 180:
                    continue


                if not (
                    1 <= len(numero) <= 4
                ):
                    continue


                numeros.append(
                    (
                        item["x"],
                        numero
                    )
                )


            numeros.sort(
                key=lambda x: x[0]
            )


            # No título eleitoral:
            # título -> zona -> seção
            posteriores = [
                numero
                for x, numero in numeros
                if x > item_titulo["x"]
            ]


            if (
                not zona
                and len(
                    posteriores
                ) >= 1
            ):

                zona = posteriores[
                    0
                ]


            if (
                not secao
                and len(
                    posteriores
                ) >= 2
            ):

                secao = posteriores[
                    1
                ]


    return (
        zona,
        secao
    )


# ============================================================
# 19. EXTRAIR DADOS
# ============================================================

def extrair_dados(
    texto,
    itens
):

    titulo = encontrar_titulo(
        itens
    )


    nome = encontrar_nome(
        itens
    )


    cpf = encontrar_cpf(
        itens
    )


    nascimento = (
        encontrar_nascimento(
            itens
        )
    )


    zona, secao = (
        encontrar_zona_secao(
            itens,
            titulo
        )
    )


    return {

        "nome":
            nome,

        "cpf":
            cpf,

        "titulo":
            titulo,

        "data_nascimento":
            nascimento,

        "zona":
            zona,

        "secao":
            secao
    }


# ============================================================
# 20. CARREGAR BASE DO SHEETS
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
# 21. VERIFICAR DUPLICIDADE
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

        titulo_existente = (
            somente_numeros(
                pessoa.get(
                    "titulo",
                    ""
                )
            )
        )


        cpf_existente = (
            somente_numeros(
                pessoa.get(
                    "cpf",
                    ""
                )
            )
        )


        if (
            titulo_novo
            and titulo_existente
            and titulo_novo.lstrip("0")
            == titulo_existente.lstrip("0")
        ):

            return (
                True,
                pessoa
            )


        if (
            cpf_novo
            and cpf_existente
            and cpf_novo
            == cpf_existente
        ):

            return (
                True,
                pessoa
            )


    return (
        False,
        None
    )


# ============================================================
# 22. SUPERVISORES
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
            and sup
            not in supervisores
        ):

            supervisores.append(
                sup
            )


        if (
            sub
            and sub
            not in subs
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
# 23. CABEÇALHO
# ============================================================

st.title(
    "📋 Sistema de Cadastro CP"
)

st.caption(
    "Leitura e conferência de documentos"
)

st.markdown("---")


# ============================================================
# 24. BASE
# ============================================================

base = carregar_base()


lista_sup, lista_sub = (
    obter_supervisores(
        base
    )
)


# ============================================================
# 25. SIDEBAR
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

        supervisor = (
            st.text_input(
                "Novo Supervisor"
            ).upper()
        )

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

        sub = (
            st.text_input(
                "Novo Sub"
            ).upper()
        )

    else:

        sub = sub_opcao


    st.markdown("---")


    menu = st.radio(
        "Escolha a Operação:",
        [
            "📸 Envio de Documentos",
            "✍️ Formulário Manual"
        ]
    )


# ============================================================
# 26. ENVIO EM LOTE
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
            "Os documentos serão processados "
            "individualmente para reduzir o uso de memória."
        )


        if st.button(
            "🔎 Processar Lote"
        ):

            resultados = []


            # ================================================
            # CARREGA OCR UMA VEZ
            # ================================================

            with st.spinner(
                "Preparando leitor de documentos..."
            ):

                try:

                    leitor = carregar_ocr()

                except Exception as erro:

                    st.error(
                        "Não foi possível inicializar "
                        "o OCR."
                    )

                    st.exception(
                        erro
                    )

                    st.stop()


            total = len(
                arquivos
            )


            barra = st.progress(
                0
            )


            status_area = st.empty()


            # ================================================
            # PROCESSAMENTO UM POR UM
            # ================================================

            for indice, arquivo in enumerate(
                arquivos
            ):

                status_area.info(
                    f"Processando "
                    f"{indice + 1} de {total}: "
                    f"{arquivo.name}"
                )


                try:

                    texto, itens, tipo = (
                        ler_documento(
                            arquivo,
                            leitor
                        )
                    )


                    dados = (
                        extrair_dados(
                            texto,
                            itens
                        )
                    )


                    duplicado, existente = (
                        verificar_duplicidade(
                            dados,
                            base
                        )
                    )


                    # ========================================
                    # CLASSIFICA RESULTADO
                    # ========================================

                    if duplicado:

                        resultado = (
                            "⚠️ JÁ CADASTRADO"
                        )

                        existente_nome = (
                            existente.get(
                                "nome",
                                ""
                            )
                        )

                        existente_sup = (
                            existente.get(
                                "supervisor",
                                ""
                            )
                        )


                    elif (
                        not dados["nome"]
                        or (
                            not dados["titulo"]
                            and not dados["cpf"]
                        )
                    ):

                        resultado = (
                            "❌ CONFERIR"
                        )

                        existente_nome = ""

                        existente_sup = ""


                    else:

                        resultado = (
                            "✅ NOVO"
                        )

                        existente_nome = ""

                        existente_sup = ""


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
                                existente_sup
                        }
                    )


                    # Libera dados intermediários
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


                barra.progress(
                    (
                        indice + 1
                    )
                    / total
                )


                gc.collect()


            # ================================================
            # TERMINOU
            # ================================================

            status_area.success(
                "Processamento concluído."
            )


            st.session_state[
                "resultado_lote"
            ] = resultados


# ============================================================
# 27. RESULTADO DO LOTE
# ============================================================

    if (
        "resultado_lote"
        in st.session_state
    ):

        resultados = (
            st.session_state[
                "resultado_lote"
            ]
        )


        if resultados:

            st.markdown("---")

            st.subheader(
                "📊 Resultado do Lote"
            )


            novos = sum(
                1
                for r in resultados
                if r["Resultado"]
                == "✅ NOVO"
            )


            duplicados = sum(
                1
                for r in resultados
                if r["Resultado"]
                == "⚠️ JÁ CADASTRADO"
            )


            conferir = sum(
                1
                for r in resultados
                if r["Resultado"]
                in [
                    "❌ CONFERIR",
                    "❌ ERRO"
                ]
            )


            col1, col2, col3 = (
                st.columns(3)
            )


            col1.metric(
                "Novos",
                novos
            )


            col2.metric(
                "Já cadastrados",
                duplicados
            )


            col3.metric(
                "Conferir",
                conferir
            )


            df_resultados = (
                pd.DataFrame(
                    resultados
                )
            )


            st.dataframe(
                df_resultados,
                use_container_width=True,
                hide_index=True
            )


            st.caption(
                "ℹ️ Nesta etapa o sistema apenas "
                "confere os documentos. "
                "Nenhum cadastro do lote foi gravado "
                "automaticamente."
            )


# ============================================================
# 28. FORMULÁRIO MANUAL
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


        titulo_pesquisado = (
            somente_numeros(
                titulo_input
            ).lstrip("0")
        )


        encontrado = None


        for pessoa in base:

            titulo_base = (
                somente_numeros(
                    pessoa.get(
                        "titulo",
                        ""
                    )
                ).lstrip("0")
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

            e = (
                st.session_state.encontrado
            )


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

                st.session_state.titulo = (
                    ""
                )

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


                salvar = (
                    st.form_submit_button(
                        "💾 Salvar"
                    )
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

                            "supervisor":
                                supervisor,

                            "subsupervisor":
                                sub
                        }


                        try:

                            resposta = (
                                requests.post(
                                    WEBHOOK_URL,
                                    json=payload,
                                    timeout=30
                                )
                            )


                            resultado = (
                                resposta.json()
                            )


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


                                st.session_state.titulo = (
                                    ""
                                )


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
