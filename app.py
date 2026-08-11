import streamlit as st
import requests
import re
import io
import numpy as np
from PIL import Image, ImageOps
import fitz


# ============================================================
# 1. CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Sistema de Cadastro CP",
    layout="centered",
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
        border-radius: 15px !important;
        border: 2px solid #0056b3 !important;
        font-weight: bold !important;
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
# 4. FUNÇÕES AUXILIARES
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
# 5. CARREGAR OCR SOMENTE QUANDO FOR NECESSÁRIO
# ============================================================

@st.cache_resource(show_spinner=False)
def carregar_ocr():

    import easyocr

    leitor = easyocr.Reader(
        ["pt", "en"],
        gpu=False,
        verbose=False
    )

    return leitor


# ============================================================
# 6. PREPARAR IMAGEM
# ============================================================

def preparar_imagem(imagem):

    imagem = ImageOps.exif_transpose(
        imagem
    )

    imagem = imagem.convert("RGB")

    largura, altura = imagem.size

    # Evita imagem pequena demais
    if largura < 1400:

        proporcao = 1400 / largura

        nova_largura = int(
            largura * proporcao
        )

        nova_altura = int(
            altura * proporcao
        )

        imagem = imagem.resize(
            (
                nova_largura,
                nova_altura
            ),
            Image.Resampling.LANCZOS
        )

    # Evita imagens gigantes consumindo muita memória
    if imagem.width > 2500:

        proporcao = 2500 / imagem.width

        imagem = imagem.resize(
            (
                2500,
                int(imagem.height * proporcao)
            ),
            Image.Resampling.LANCZOS
        )

    return imagem


# ============================================================
# 7. PDF PARA IMAGENS
# ============================================================

def pdf_para_imagens(arquivo):

    imagens = []

    bytes_pdf = arquivo.getvalue()

    documento = fitz.open(
        stream=bytes_pdf,
        filetype="pdf"
    )

    for pagina in documento:

        # Resolução suficiente para OCR
        # sem exagerar no uso de memória.
        pix = pagina.get_pixmap(
            matrix=fitz.Matrix(2, 2),
            alpha=False
        )

        imagem = Image.open(
            io.BytesIO(
                pix.tobytes("png")
            )
        ).convert("RGB")

        imagens.append(imagem)

    documento.close()

    return imagens


# ============================================================
# 8. EXECUTAR OCR
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

    diagnostico = []

    for item in resultado:

        try:

            caixa = item[0]

            texto = str(
                item[1]
            ).strip()

            confianca = float(
                item[2]
            )

            if texto:

                # Centro aproximado da caixa
                xs = [
                    ponto[0]
                    for ponto in caixa
                ]

                ys = [
                    ponto[1]
                    for ponto in caixa
                ]

                centro_x = sum(xs) / len(xs)
                centro_y = sum(ys) / len(ys)

                itens.append(
                    {
                        "texto": texto,
                        "confianca": confianca,
                        "x": centro_x,
                        "y": centro_y
                    }
                )

                diagnostico.append(
                    f"{confianca:.2%} | {texto}"
                )

        except Exception as erro:

            diagnostico.append(
                f"Erro ao interpretar linha: {erro}"
            )


    # Ordena aproximadamente de cima para baixo
    itens.sort(
        key=lambda item: (
            item["y"],
            item["x"]
        )
    )

    textos = [
        item["texto"]
        for item in itens
    ]

    texto_final = "\n".join(
        textos
    )

    diagnostico_final = "\n".join(
        diagnostico
    )

    return (
        texto_final,
        diagnostico_final,
        itens
    )


# ============================================================
# 9. LER DOCUMENTO
# ============================================================

def ler_documento(
    arquivo,
    leitor
):

    nome = arquivo.name.lower()

    textos = []

    diagnosticos = []

    todos_itens = []


    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    if nome.endswith(".pdf"):

        imagens = pdf_para_imagens(
            arquivo
        )

        for numero_pagina, imagem in enumerate(
            imagens,
            start=1
        ):

            texto, diagnostico, itens = (
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

            diagnosticos.append(
                f"===== PÁGINA {numero_pagina} =====\n"
                f"{diagnostico}"
            )


    # --------------------------------------------------------
    # FOTO
    # --------------------------------------------------------

    else:

        arquivo.seek(0)

        imagem = Image.open(
            arquivo
        )

        texto, diagnostico, itens = (
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

        diagnosticos.append(
            diagnostico
        )


    return (
        "\n".join(textos),
        "\n\n".join(diagnosticos),
        todos_itens
    )


# ============================================================
# 10. IDENTIFICAR NÚMEROS DO TÍTULO
# ============================================================

def encontrar_titulo(itens):

    candidatos = []

    for item in itens:

        texto = item["texto"]

        numeros = somente_numeros(
            texto
        )

        # Título eleitoral possui 12 dígitos
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

        return candidatos[0][1]

    return ""


# ============================================================
# 11. IDENTIFICAR DATA DE NASCIMENTO
# ============================================================

def encontrar_nascimento(itens):

    for item in itens:

        texto = item["texto"]

        match = re.search(
            r"\b"
            r"(\d{2})"
            r"[\/.\-]"
            r"(\d{2})"
            r"[\/.\-]"
            r"(\d{4})"
            r"\b",
            texto
        )

        if match:

            dia = match.group(1)
            mes = match.group(2)
            ano = match.group(3)

            try:

                ano_int = int(ano)

                # Evita pegar datas absurdas
                if 1900 <= ano_int <= 2026:

                    return (
                        f"{dia}/{mes}/{ano}"
                    )

            except Exception:
                pass

    return ""


# ============================================================
# 12. IDENTIFICAR CPF
# ============================================================

def encontrar_cpf(itens):

    for item in itens:

        texto = item["texto"]

        numeros = somente_numeros(
            texto
        )

        if len(numeros) == 11:

            return formatar_cpf(
                numeros
            )

    return ""


# ============================================================
# 13. IDENTIFICAR NOME
# ============================================================

def parece_nome(texto):

    texto = texto.strip()

    texto_upper = texto.upper()

    if not texto:
        return False

    if re.search(
        r"\d",
        texto
    ):
        return False

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
        "NOME",
        "DATA DE NASCIMENTO",
        "NASCIMENTO",
        "INSCRIÇÃO",
        "INSCRICAO",
        "ZONA",
        "SEÇÃO",
        "SECAO",
        "MUNICIPIO",
        "MUNICÍPIO",
        "DATA DE EMISSAO",
        "DATA DE EMISSÃO",
        "VALIDO SOMENTE",
        "VÁLIDO SOMENTE",
        "MARCA D'AGUA",
        "MARCA D'ÁGUA"
    ]

    for termo in ignorar:

        if termo in texto_upper:
            return False


    palavras = texto.split()

    if len(palavras) < 2:
        return False

    if len(palavras) > 8:
        return False


    letras = re.sub(
        r"[^A-Za-zÀ-ÿ]",
        "",
        texto
    )

    if len(letras) < 8:
        return False

    return True


def encontrar_nome(itens):

    # --------------------------------------------------------
    # PRIMEIRA TENTATIVA:
    # procura a posição do rótulo NOME DO ELEITOR
    # --------------------------------------------------------

    indice_nome = None

    for i, item in enumerate(
        itens
    ):

        texto = normalizar_texto(
            item["texto"]
        )

        texto_sem_espacos = re.sub(
            r"[^A-ZÀ-Ú]",
            "",
            texto
        )

        if (
            "NOMEDOELEITOR"
            in texto_sem_espacos
            or texto_sem_espacos
            == "NOME"
        ):

            indice_nome = i
            break


    if indice_nome is not None:

        proximos = itens[
            indice_nome + 1:
            indice_nome + 7
        ]

        for item in proximos:

            candidato = item[
                "texto"
            ].strip()

            if parece_nome(
                candidato
            ):

                return candidato.upper()


    # --------------------------------------------------------
    # SEGUNDA TENTATIVA:
    # procura melhor candidato geral
    # --------------------------------------------------------

    candidatos = []

    for item in itens:

        candidato = item[
            "texto"
        ].strip()

        if parece_nome(
            candidato
        ):

            quantidade_palavras = len(
                candidato.split()
            )

            pontuacao = (
                quantidade_palavras * 10
                + len(candidato)
                + item["confianca"] * 10
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
# 14. IDENTIFICAR ZONA E SEÇÃO
# ============================================================

def encontrar_zona_secao(
    itens,
    titulo
):

    zona = ""
    secao = ""

    # --------------------------------------------------------
    # Primeiro procura os rótulos ZONA e SEÇÃO
    # --------------------------------------------------------

    item_zona = None
    item_secao = None

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

        if (
            texto_limpo == "SECAO"
            or texto_limpo == "SEÇÃO"
        ):
            item_secao = item


    # --------------------------------------------------------
    # Procura números abaixo dos respectivos rótulos
    # --------------------------------------------------------

    if item_zona:

        candidatos_zona = []

        for item in itens:

            numero = somente_numeros(
                item["texto"]
            )

            if not numero:
                continue

            if numero == titulo:
                continue

            if not (
                1 <= len(numero) <= 3
            ):
                continue

            if item["y"] <= item_zona["y"]:
                continue

            distancia_vertical = (
                item["y"]
                - item_zona["y"]
            )

            distancia_horizontal = abs(
                item["x"]
                - item_zona["x"]
            )

            if distancia_vertical < 500:

                pontuacao = (
                    distancia_vertical
                    + distancia_horizontal
                )

                candidatos_zona.append(
                    (
                        pontuacao,
                        numero
                    )
                )


        if candidatos_zona:

            candidatos_zona.sort()

            zona = candidatos_zona[
                0
            ][1]


    if item_secao:

        candidatos_secao = []

        for item in itens:

            numero = somente_numeros(
                item["texto"]
            )

            if not numero:
                continue

            if numero == titulo:
                continue

            if not (
                1 <= len(numero) <= 4
            ):
                continue

            if item["y"] <= item_secao["y"]:
                continue

            distancia_vertical = (
                item["y"]
                - item_secao["y"]
            )

            distancia_horizontal = abs(
                item["x"]
                - item_secao["x"]
            )

            if distancia_vertical < 500:

                pontuacao = (
                    distancia_vertical
                    + distancia_horizontal
                )

                candidatos_secao.append(
                    (
                        pontuacao,
                        numero
                    )
                )


        if candidatos_secao:

            candidatos_secao.sort()

            secao = candidatos_secao[
                0
            ][1]


    # --------------------------------------------------------
    # FALLBACK PARA E-TÍTULO/TÍTULO ELEITORAL
    #
    # Depois do título de 12 dígitos normalmente aparecem
    # zona (até 3 dígitos) e seção (até 4 dígitos).
    # --------------------------------------------------------

    if (
        not zona
        or not secao
    ):

        indice_titulo = None

        for i, item in enumerate(
            itens
        ):

            numero = somente_numeros(
                item["texto"]
            )

            if (
                titulo
                and numero == titulo
            ):

                indice_titulo = i
                break


        if indice_titulo is not None:

            numeros_depois = []

            for item in itens[
                indice_titulo + 1:
                indice_titulo + 8
            ]:

                numero = somente_numeros(
                    item["texto"]
                )

                if not numero:
                    continue

                # Ignora datas
                if re.search(
                    r"\d{2}[\/.\-]\d{2}[\/.\-]\d{4}",
                    item["texto"]
                ):
                    continue

                if 1 <= len(numero) <= 4:

                    numeros_depois.append(
                        numero
                    )


            if (
                not zona
                and len(numeros_depois) >= 1
            ):

                zona = numeros_depois[0]


            if (
                not secao
                and len(numeros_depois) >= 2
            ):

                secao = numeros_depois[1]


    return (
        zona,
        secao
    )


# ============================================================
# 15. EXTRAIR TODOS OS DADOS
# ============================================================

def extrair_dados(
    texto,
    itens
):

    titulo = encontrar_titulo(
        itens
    )

    nascimento = encontrar_nascimento(
        itens
    )

    cpf = encontrar_cpf(
        itens
    )

    nome = encontrar_nome(
        itens
    )

    zona, secao = (
        encontrar_zona_secao(
            itens,
            titulo
        )
    )


    return {
        "nome": nome,
        "cpf": cpf,
        "titulo": titulo,
        "data_nascimento": nascimento,
        "zona": zona,
        "secao": secao
    }


# ============================================================
# 16. CARREGAR SUPERVISORES
# ============================================================

@st.cache_data(ttl=60)
def carregar_supervisores_rapido():

    supervisores_encontrados = []

    subs_encontrados = [
        "SEM SUBSUPERVISOR"
    ]


    try:

        response = requests.get(
            WEBHOOK_URL,
            timeout=8
        )


        if response.status_code == 200:

            dados = response.json()


            if isinstance(
                dados,
                list
            ):

                for item in dados:

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
                        not in supervisores_encontrados
                    ):

                        supervisores_encontrados.append(
                            sup
                        )


                    if (
                        sub
                        and sub
                        not in subs_encontrados
                    ):

                        subs_encontrados.append(
                            sub
                        )


    except Exception:
        pass


    return (
        sorted(
            supervisores_encontrados
        ),
        sorted(
            subs_encontrados
        )
    )


# ============================================================
# 17. CABEÇALHO
# ============================================================

st.title(
    "📋 Sistema de Cadastro CP"
)

st.markdown("---")


# ============================================================
# 18. SIDEBAR
# ============================================================

lista_sup, lista_sub = (
    carregar_supervisores_rapido()
)


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
# 19. ENVIO DE DOCUMENTOS
# ============================================================

if menu == "📸 Envio de Documentos":

    st.markdown(
        f"#### 📁 Leitura Automática — "
        f"**Sup:** {supervisor} | "
        f"**Sub:** {sub}"
    )


    st.info(
        "💡 Envie JPG, PNG ou PDF. "
        "Nesta etapa estamos validando a leitura; "
        "nada será cadastrado automaticamente."
    )


    arquivos = st.file_uploader(
        "Arraste fotos ou PDFs",
        accept_multiple_files=True,
        type=[
            "pdf",
            "jpg",
            "jpeg",
            "png"
        ]
    )


    if arquivos:

        # ----------------------------------------------------
        # PREVIEW ANTES DE CARREGAR OCR
        # ----------------------------------------------------

        for arquivo in arquivos:

            if not arquivo.name.lower().endswith(
                ".pdf"
            ):

                try:

                    arquivo.seek(0)

                    preview = Image.open(
                        arquivo
                    )

                    preview = (
                        ImageOps.exif_transpose(
                            preview
                        )
                    )

                    st.image(
                        preview,
                        caption=arquivo.name,
                        width=450
                    )

                    arquivo.seek(0)

                except Exception:
                    pass


        if st.button(
            "🔎 Ler Documentos"
        ):

            # ================================================
            # OCR SÓ É CARREGADO AQUI
            # ================================================

            with st.spinner(
                "Inicializando leitor de documentos..."
            ):

                try:

                    leitor = carregar_ocr()

                except Exception as erro:

                    st.error(
                        "Não foi possível inicializar "
                        "o leitor OCR."
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


            for i, arquivo in enumerate(
                arquivos
            ):

                st.markdown("---")

                st.subheader(
                    f"📄 {arquivo.name}"
                )


                try:

                    with st.spinner(
                        f"Lendo {arquivo.name}..."
                    ):

                        texto, diagnostico, itens = (
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


                    # ========================================
                    # RESULTADO
                    # ========================================

                    if texto:

                        st.success(
                            "Texto encontrado no documento."
                        )

                    else:

                        st.warning(
                            "Nenhum texto foi reconhecido."
                        )


                    st.markdown(
                        "### 🔍 Dados identificados"
                    )


                    col1, col2 = (
                        st.columns(2)
                    )


                    with col1:

                        st.write(
                            "**Nome:**",
                            dados["nome"]
                            or "Não identificado"
                        )

                        st.write(
                            "**CPF:**",
                            dados["cpf"]
                            or "Não identificado"
                        )

                        st.write(
                            "**Título:**",
                            dados["titulo"]
                            or "Não identificado"
                        )


                    with col2:

                        st.write(
                            "**Nascimento:**",
                            dados[
                                "data_nascimento"
                            ]
                            or "Não identificado"
                        )

                        st.write(
                            "**Zona:**",
                            dados["zona"]
                            or "Não identificada"
                        )

                        st.write(
                            "**Seção:**",
                            dados["secao"]
                            or "Não identificada"
                        )


                    # ========================================
                    # TEXTO COMPLETO
                    # ========================================

                    with st.expander(
                        "📝 Ver texto reconhecido"
                    ):

                        if texto:

                            st.text_area(
                                "Resultado OCR",
                                texto,
                                height=300,
                                key=f"texto_{i}"
                            )

                        else:

                            st.write(
                                "Nenhum texto reconhecido."
                            )


                    # ========================================
                    # DIAGNÓSTICO
                    # ========================================

                    with st.expander(
                        "🛠️ Diagnóstico da leitura"
                    ):

                        if diagnostico:

                            st.code(
                                diagnostico
                            )

                        else:

                            st.write(
                                "Nenhuma informação."
                            )


                except Exception as erro:

                    st.error(
                        f"Erro ao processar "
                        f"{arquivo.name}: {erro}"
                    )

                    st.exception(
                        erro
                    )


                barra.progress(
                    (i + 1) / total
                )


# ============================================================
# 20. FORMULÁRIO MANUAL
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
                "busca_realizada": False,
                "titulo": "",
                "encontrado": None
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

        st.session_state.busca_realizada = (
            True
        )


        try:

            dados_base = requests.get(
                WEBHOOK_URL,
                timeout=5
            ).json()


            titulo_pesquisado = re.sub(
                r"\D",
                "",
                titulo_input
            ).lstrip("0")


            st.session_state.encontrado = next(
                (
                    r
                    for r in dados_base
                    if re.sub(
                        r"\D",
                        "",
                        str(
                            r.get(
                                "titulo",
                                ""
                            )
                        )
                    ).lstrip("0")
                    == titulo_pesquisado
                ),
                None
            )


        except Exception:

            st.session_state.encontrado = (
                None
            )


    if st.session_state.busca_realizada:

        if st.session_state.encontrado:

            e = (
                st.session_state.encontrado
            )

            st.error(
                f"⚠️ Já cadastrado: "
                f"{e.get('nome')} | "
                f"Sup: {e.get('supervisor')}"
            )


            if st.button(
                "Limpar"
            ):

                st.session_state.busca_realizada = (
                    False
                )

                st.rerun()


        else:

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

                            resposta = requests.post(
                                WEBHOOK_URL,
                                json=payload,
                                timeout=30
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

                                st.session_state.busca_realizada = (
                                    False
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
