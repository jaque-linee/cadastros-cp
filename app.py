import streamlit as st
import requests
import re
import io
from PIL import Image
from paddleocr import PaddleOCR
import fitz  # PyMuPDF


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
# 4. OCR
# ============================================================

@st.cache_resource
def carregar_ocr():
    return PaddleOCR(
        lang="pt",
        use_doc_orientation_classify=True,
        use_doc_unwarping=True,
        use_textline_orientation=True
    )


def pdf_para_imagens(arquivo):
    imagens = []

    bytes_pdf = arquivo.getvalue()
    documento = fitz.open(stream=bytes_pdf, filetype="pdf")

    for pagina in documento:
        pix = pagina.get_pixmap(matrix=fitz.Matrix(2, 2))

        imagem = Image.open(
            io.BytesIO(pix.tobytes("png"))
        ).convert("RGB")

        imagens.append(imagem)

    documento.close()

    return imagens


def executar_ocr_imagem(imagem):
    ocr = carregar_ocr()

    resultado = ocr.predict(imagem)

    textos = []

    for pagina in resultado:
        try:
            dados = pagina.json

            if callable(dados):
                dados = dados()

            if isinstance(dados, str):
                import json
                dados = json.loads(dados)

            res = dados.get("res", dados)

            rec_texts = res.get("rec_texts", [])

            for texto in rec_texts:
                if texto:
                    textos.append(str(texto))

        except Exception:
            pass

    return "\n".join(textos)


def ler_documento(arquivo):
    nome = arquivo.name.lower()

    if nome.endswith(".pdf"):
        imagens = pdf_para_imagens(arquivo)

        textos_paginas = []

        for imagem in imagens:
            texto = executar_ocr_imagem(imagem)

            if texto:
                textos_paginas.append(texto)

        return "\n".join(textos_paginas)

    imagem = Image.open(arquivo).convert("RGB")

    return executar_ocr_imagem(imagem)


# ============================================================
# 5. EXTRAÇÃO DOS CAMPOS
# ============================================================

def somente_numeros(valor):
    return re.sub(r"\D", "", str(valor or ""))


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
        dados["cpf"] = somente_numeros(cpf_match.group())


    # --------------------------------------------------------
    # TÍTULO DE ELEITOR
    # --------------------------------------------------------

    padroes_titulo = [
        r"(?:INSCRIÇÃO|INSCRICAO)[^\d]{0,20}(\d[\d\s.-]{9,15}\d)",
        r"(?:TÍTULO|TITULO)[^\d]{0,20}(\d[\d\s.-]{9,15}\d)"
    ]

    for padrao in padroes_titulo:
        match = re.search(
            padrao,
            texto,
            flags=re.IGNORECASE
        )

        if match:
            numero = somente_numeros(match.group(1))

            if len(numero) == 12:
                dados["titulo"] = numero
                break


    # --------------------------------------------------------
    # DATA DE NASCIMENTO
    # --------------------------------------------------------

    nascimento_match = re.search(
        r"(?:NASCIMENTO|DATA DE NASCIMENTO|NASC)[^\d]{0,20}"
        r"(\d{2}[\/.-]\d{2}[\/.-]\d{4})",
        texto,
        flags=re.IGNORECASE
    )

    if nascimento_match:
        dados["data_nascimento"] = (
            nascimento_match
            .group(1)
            .replace(".", "/")
            .replace("-", "/")
        )


    # --------------------------------------------------------
    # ZONA
    # --------------------------------------------------------

    zona_match = re.search(
        r"\bZONA\b[^\d]{0,10}(\d{1,3})",
        texto,
        flags=re.IGNORECASE
    )

    if zona_match:
        dados["zona"] = zona_match.group(1)


    # --------------------------------------------------------
    # SEÇÃO
    # --------------------------------------------------------

    secao_match = re.search(
        r"\bSE[ÇC][ÃA]O\b[^\d]{0,10}(\d{1,4})",
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
                candidato = linhas[i + 1].strip()

                if len(candidato) >= 5:
                    dados["nome"] = candidato.upper()
                    break

    return dados


# ============================================================
# 6. SUPERVISORES E SUBSUPERVISORES
# ============================================================

@st.cache_data(ttl=60)
def carregar_supervisores_rapido():

    supervisores_encontrados = []
    subs_encontrados = ["SEM SUBSUPERVISOR"]

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
                        item.get("supervisor", "")
                    ).strip().upper()

                    sub = str(
                        item.get("subsupervisor", "")
                    ).strip().upper()

                    if (
                        sup
                        and sup not in supervisores_encontrados
                    ):
                        supervisores_encontrados.append(sup)

                    if (
                        sub
                        and sub not in subs_encontrados
                    ):
                        subs_encontrados.append(sub)

    except Exception:
        pass

    return (
        sorted(supervisores_encontrados),
        sorted(subs_encontrados)
    )


# ============================================================
# 7. CABEÇALHO
# ============================================================

st.title("📋 Sistema de Cadastro CP")

st.markdown("---")


# ============================================================
# 8. SIDEBAR
# ============================================================

lista_sup, lista_sub = carregar_supervisores_rapido()


with st.sidebar:

    st.header("⚙️ Configuração")

    sup_opcao = st.selectbox(
        "Supervisor",
        lista_sup + ["➕ Cadastrar Novo Supervisor"]
    )

    if sup_opcao == "➕ Cadastrar Novo Supervisor":
        supervisor = st.text_input(
            "Novo Supervisor"
        ).upper()
    else:
        supervisor = sup_opcao


    sub_opcao = st.selectbox(
        "Subsupervisor",
        lista_sub + ["➕ Cadastrar Novo Sub"]
    )

    if sub_opcao == "➕ Cadastrar Novo Sub":
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
# 9. ENVIO DE DOCUMENTOS
# ============================================================

if menu == "📸 Envio de Documentos":

    st.markdown(
        f"#### 📁 Leitura Automática — "
        f"**Sup:** {supervisor} | "
        f"**Sub:** {sub}"
    )

    st.info(
        "💡 Nesta etapa vamos testar a leitura. "
        "Nada será cadastrado no Sheets."
    )

    arquivos = st.file_uploader(
        "Arraste fotos ou PDFs",
        accept_multiple_files=True,
        type=["pdf", "jpg", "jpeg", "png"]
    )


    if arquivos:

        if st.button("🔎 Ler Documentos"):

            total = len(arquivos)

            barra = st.progress(0)

            for i, arquivo in enumerate(arquivos):

                st.markdown("---")

                st.subheader(
                    f"📄 {arquivo.name}"
                )

                try:

                    with st.spinner(
                        f"Lendo {arquivo.name}..."
                    ):

                        texto = ler_documento(arquivo)

                        dados = extrair_dados(texto)


                    st.markdown("### 🔍 Dados identificados")

                    col1, col2 = st.columns(2)

                    with col1:

                        st.write(
                            "**Nome:**",
                            dados["nome"] or "Não identificado"
                        )

                        st.write(
                            "**CPF:**",
                            dados["cpf"] or "Não identificado"
                        )

                        st.write(
                            "**Título:**",
                            dados["titulo"] or "Não identificado"
                        )


                    with col2:

                        st.write(
                            "**Nascimento:**",
                            dados["data_nascimento"]
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


                    with st.expander(
                        "📝 Ver texto completo reconhecido pelo OCR"
                    ):

                        if texto:
                            st.text(texto)
                        else:
                            st.warning(
                                "Nenhum texto foi reconhecido."
                            )


                except Exception as ex:

                    st.error(
                        f"Erro ao processar "
                        f"{arquivo.name}: {ex}"
                    )


                barra.progress(
                    (i + 1) / total
                )


# ============================================================
# 10. FORMULÁRIO MANUAL
# ============================================================

elif menu == "✍️ Formulário Manual":

    st.subheader(
        "✍️ Consulta & Cadastro Manual"
    )


    if "busca_realizada" not in st.session_state:

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


    if st.button("🔍 Pesquisar"):

        st.session_state.titulo = titulo_input

        st.session_state.busca_realizada = True

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
                        str(r.get("titulo", ""))
                    ).lstrip("0")
                    == titulo_pesquisado
                ),
                None
            )

        except Exception:

            st.session_state.encontrado = None


    if st.session_state.busca_realizada:

        if st.session_state.encontrado:

            e = st.session_state.encontrado

            st.error(
                f"⚠️ Já cadastrado: "
                f"{e.get('nome')} | "
                f"Sup: {e.get('supervisor')}"
            )

            if st.button("Limpar"):

                st.session_state.busca_realizada = False

                st.rerun()


        else:

            with st.form("cadastro_manual"):

                nome = st.text_input("Nome *")

                cpf = st.text_input("CPF")

                data_nasc = st.text_input(
                    "Data de Nascimento (DD/MM/AAAA)"
                )


                salvar = st.form_submit_button(
                    "💾 Salvar"
                )


                if salvar:

                    if nome:

                        payload = {
                            "titulo": st.session_state.titulo,
                            "nome": nome,
                            "cpf": cpf,
                            "data_nascimento": data_nasc,
                            "supervisor": supervisor,
                            "subsupervisor": sub
                        }

                        try:

                            resposta = requests.post(
                                WEBHOOK_URL,
                                json=payload,
                                timeout=30
                            )

                            resultado = resposta.json()

                            if (
                                resultado.get("status")
                                == "SUCESSO"
                            ):

                                st.success(
                                    "Salvo com sucesso!"
                                )

                                st.session_state.busca_realizada = False

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
                                f"Erro ao salvar: {ex}"
                            )
