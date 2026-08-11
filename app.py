import streamlit as st
import requests
import re
import io
import json
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR
import fitz


# ============================================================
# 1. CONFIGURAÇÃO DA PÁGINA
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
    st.error("Erro nas chaves de segurança (Secrets) do Streamlit.")
    st.stop()


# ============================================================
# 4. CARREGAR OCR
# ============================================================

@st.cache_resource
def carregar_ocr():
    return PaddleOCR(
        lang="pt",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False
    )


# ============================================================
# 5. CONVERTER PDF PARA IMAGENS
# ============================================================

def pdf_para_imagens(arquivo):
    imagens = []

    bytes_pdf = arquivo.getvalue()

    documento = fitz.open(
        stream=bytes_pdf,
        filetype="pdf"
    )

    for pagina in documento:
        pix = pagina.get_pixmap(
            matrix=fitz.Matrix(2, 2),
            alpha=False
        )

        imagem = Image.open(
            io.BytesIO(pix.tobytes("png"))
        ).convert("RGB")

        imagens.append(imagem)

    documento.close()

    return imagens


# ============================================================
# 6. EXECUTAR OCR
# ============================================================

def executar_ocr_imagem(imagem):
    ocr = carregar_ocr()

    # Converte a imagem PIL para array NumPy
    imagem_np = np.array(imagem)

    resultado = ocr.predict(imagem_np)

    textos = []
    diagnostico = []

    for pagina in resultado:

        # ----------------------------------------------------
        # TENTA OBTER O RESULTADO COMO DICIONÁRIO
        # ----------------------------------------------------

        dados = None

        try:
            dados = pagina.json

            if callable(dados):
                dados = dados()

        except Exception as erro:
            diagnostico.append(
                f"Erro ao acessar pagina.json: {erro}"
            )


        # ----------------------------------------------------
        # SE VEIO COMO STRING JSON
        # ----------------------------------------------------

        if isinstance(dados, str):
            try:
                dados = json.loads(dados)
            except Exception as erro:
                diagnostico.append(
                    f"Erro ao converter JSON: {erro}"
                )


        # ----------------------------------------------------
        # GUARDA INFORMAÇÃO PARA DIAGNÓSTICO
        # ----------------------------------------------------

        try:
            diagnostico.append(
                "TIPO DA RESPOSTA: "
                + str(type(pagina))
            )

            diagnostico.append(
                "DADOS JSON: "
                + str(dados)
            )

        except Exception:
            pass


        # ----------------------------------------------------
        # FORMATO PADDLEOCR 3.X
        # ----------------------------------------------------

        if isinstance(dados, dict):

            res = dados.get("res", dados)

            if isinstance(res, dict):

                rec_texts = res.get(
                    "rec_texts",
                    []
                )

                if rec_texts:

                    for texto in rec_texts:
                        texto = str(texto).strip()

                        if texto:
                            textos.append(texto)


        # ----------------------------------------------------
        # SEGUNDA TENTATIVA:
        # ACESSAR O OBJETO DIRETAMENTE
        # ----------------------------------------------------

        if not textos:

            try:
                if hasattr(pagina, "get"):

                    rec_texts = pagina.get(
                        "rec_texts",
                        []
                    )

                    for texto in rec_texts:

                        texto = str(texto).strip()

                        if texto:
                            textos.append(texto)

            except Exception as erro:

                diagnostico.append(
                    "Erro na leitura direta: "
                    + str(erro)
                )


    texto_final = "\n".join(textos)

    diagnostico_final = "\n\n".join(
        diagnostico
    )

    return texto_final, diagnostico_final


# ============================================================
# 7. LER DOCUMENTO
# ============================================================

def ler_documento(arquivo):

    nome = arquivo.name.lower()

    textos = []
    diagnosticos = []


    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    if nome.endswith(".pdf"):

        imagens = pdf_para_imagens(arquivo)

        for numero_pagina, imagem in enumerate(
            imagens,
            start=1
        ):

            texto, diagnostico = executar_ocr_imagem(
                imagem
            )

            if texto:
                textos.append(texto)

            diagnosticos.append(
                f"===== PÁGINA {numero_pagina} =====\n"
                + diagnostico
            )


    # --------------------------------------------------------
    # FOTO
    # --------------------------------------------------------

    else:

        arquivo.seek(0)

        imagem = Image.open(
            arquivo
        ).convert("RGB")

        texto, diagnostico = executar_ocr_imagem(
            imagem
        )

        if texto:
            textos.append(texto)

        diagnosticos.append(
            diagnostico
        )


    return (
        "\n".join(textos),
        "\n\n".join(diagnosticos)
    )


# ============================================================
# 8. FUNÇÕES AUXILIARES
# ============================================================

def somente_numeros(valor):
    return re.sub(
        r"\D",
        "",
        str(valor or "")
    )


# ============================================================
# 9. EXTRAIR CAMPOS DO TEXTO
# ============================================================

def extrair_dados(texto):

    texto = texto or ""

    dados = {
        "nome": "",
        "cpf": "",
        "titulo": "",
        "data_nascimento": "",
        "zona": "",
        "secao": ""
    }


    # --------------------------------------------------------
    # CPF
    # --------------------------------------------------------

    cpf_match = re.search(
        r"\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2}\b",
        texto
    )

    if cpf_match:

        cpf = somente_numeros(
            cpf_match.group()
        )

        if len(cpf) == 11:
            dados["cpf"] = cpf


    # --------------------------------------------------------
    # TÍTULO
    # --------------------------------------------------------

    padroes_titulo = [
        r"(?:INSCRIÇÃO|INSCRICAO)[^\d]{0,30}(\d[\d\s.\-]{9,18}\d)",
        r"(?:TÍTULO|TITULO)[^\d]{0,30}(\d[\d\s.\-]{9,18}\d)"
    ]

    for padrao in padroes_titulo:

        match = re.search(
            padrao,
            texto,
            flags=re.IGNORECASE
        )

        if match:

            numero = somente_numeros(
                match.group(1)
            )

            if len(numero) == 12:
                dados["titulo"] = numero
                break


    # --------------------------------------------------------
    # NASCIMENTO
    # --------------------------------------------------------

    padroes_nascimento = [
        r"(?:DATA DE NASCIMENTO|NASCIMENTO|NASC)[^\d]{0,30}(\d{2}[\/.\-]\d{2}[\/.\-]\d{4})",
        r"\b(\d{2}[\/.\-]\d{2}[\/.\-]\d{4})\b"
    ]

    for padrao in padroes_nascimento:

        match = re.search(
            padrao,
            texto,
            flags=re.IGNORECASE
        )

        if match:

            dados["data_nascimento"] = (
                match.group(1)
                .replace(".", "/")
                .replace("-", "/")
            )

            break


    # --------------------------------------------------------
    # ZONA
    # --------------------------------------------------------

    zona_match = re.search(
        r"\bZONA\b[^\d]{0,15}(\d{1,3})",
        texto,
        flags=re.IGNORECASE
    )

    if zona_match:
        dados["zona"] = zona_match.group(1)


    # --------------------------------------------------------
    # SEÇÃO
    # --------------------------------------------------------

    secao_match = re.search(
        r"\bSE[ÇC][ÃA]O\b[^\d]{0,15}(\d{1,4})",
        texto,
        flags=re.IGNORECASE
    )

    if secao_match:
        dados["secao"] = secao_match.group(1)


    # --------------------------------------------------------
    # NOME
    # --------------------------------------------------------

    linhas = [
        linha.strip()
        for linha in texto.splitlines()
        if linha.strip()
    ]

    for i, linha in enumerate(linhas):

        linha_upper = linha.upper()

        if (
            "NOME DO ELEITOR" in linha_upper
            or linha_upper == "NOME"
        ):

            if i + 1 < len(linhas):

                candidato = linhas[
                    i + 1
                ].strip()

                if len(candidato) >= 5:

                    dados["nome"] = (
                        candidato.upper()
                    )

                    break


    return dados


# ============================================================
# 10. CARREGAR SUPERVISORES
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

            if isinstance(dados, list):

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
        sorted(supervisores_encontrados),
        sorted(subs_encontrados)
    )


# ============================================================
# 11. CABEÇALHO
# ============================================================

st.title(
    "📋 Sistema de Cadastro CP"
)

st.markdown("---")


# ============================================================
# 12. SIDEBAR
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


    st.markdown("---")


    menu = st.radio(
        "Escolha a Operação:",
        [
            "📸 Envio de Documentos",
            "✍️ Formulário Manual"
        ]
    )


# ============================================================
# 13. ENVIO DE DOCUMENTOS
# ============================================================

if menu == "📸 Envio de Documentos":

    st.markdown(
        f"#### 📁 Leitura Automática — "
        f"**Sup:** {supervisor} | "
        f"**Sub:** {sub}"
    )


    st.info(
        "💡 Teste de OCR. "
        "Nesta etapa nada será cadastrado "
        "no Sheets."
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

        if st.button(
            "🔎 Ler Documentos"
        ):

            total = len(arquivos)

            barra = st.progress(0)


            for i, arquivo in enumerate(
                arquivos
            ):

                st.markdown("---")

                st.subheader(
                    f"📄 {arquivo.name}"
                )


                # --------------------------------------------
                # MOSTRAR A FOTO ENVIADA
                # --------------------------------------------

                if not arquivo.name.lower().endswith(
                    ".pdf"
                ):

                    try:

                        arquivo.seek(0)

                        imagem_preview = (
                            Image.open(
                                arquivo
                            )
                        )

                        st.image(
                            imagem_preview,
                            caption="Imagem recebida pelo sistema",
                            width=500
                        )

                        arquivo.seek(0)

                    except Exception:
                        pass


                try:

                    with st.spinner(
                        f"Lendo {arquivo.name}..."
                    ):

                        texto, diagnostico = (
                            ler_documento(
                                arquivo
                            )
                        )

                        dados = extrair_dados(
                            texto
                        )


                    # ----------------------------------------
                    # TEXTO RECONHECIDO
                    # ----------------------------------------

                    st.markdown(
                        "### 📝 Texto reconhecido"
                    )


                    if texto:

                        st.success(
                            "O OCR encontrou texto."
                        )

                        st.text_area(
                            "Resultado do OCR",
                            texto,
                            height=300,
                            key=f"ocr_{i}"
                        )

                    else:

                        st.warning(
                            "Nenhum texto foi "
                            "reconhecido pelo OCR."
                        )


                    # ----------------------------------------
                    # CAMPOS IDENTIFICADOS
                    # ----------------------------------------

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


                    # ----------------------------------------
                    # DIAGNÓSTICO
                    # ----------------------------------------

                    with st.expander(
                        "🛠️ Diagnóstico técnico do OCR"
                    ):

                        if diagnostico:

                            st.code(
                                diagnostico
                            )

                        else:

                            st.write(
                                "Sem informações "
                                "de diagnóstico."
                            )


                except Exception as ex:

                    st.error(
                        "Erro ao processar "
                        f"{arquivo.name}: {ex}"
                    )

                    st.exception(ex)


                barra.progress(
                    (i + 1) / total
                )


# ============================================================
# 14. FORMULÁRIO MANUAL
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


            st.session_state.encontrado = (
                next(
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
                f"Sup: "
                f"{e.get('supervisor')}"
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

                    if nome:

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


                        except Exception as ex:

                            st.error(
                                "Erro ao salvar: "
                                f"{ex}"
                            )
