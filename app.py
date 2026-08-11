import streamlit as st
import requests
import re
import io
import numpy as np
from PIL import Image, ImageOps
import fitz
import easyocr


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
# 4. CARREGAR EASYOCR
# ============================================================

@st.cache_resource
def carregar_ocr():
    return easyocr.Reader(
        ["pt", "en"],
        gpu=False
    )


# ============================================================
# 5. PDF PARA IMAGENS
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
            matrix=fitz.Matrix(2.5, 2.5),
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
# 6. PREPARAR IMAGEM
# ============================================================

def preparar_imagem(imagem):

    imagem = ImageOps.exif_transpose(imagem)

    imagem = imagem.convert("RGB")

    largura, altura = imagem.size

    # Amplia documentos pequenos para melhorar a leitura
    if largura < 1600:

        proporcao = 1600 / largura

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

    return imagem


# ============================================================
# 7. EXECUTAR OCR
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

    linhas = []

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

                linhas.append(
                    texto
                )

                diagnostico.append(
                    f"{confianca:.2%} | {texto}"
                )

        except Exception as erro:

            diagnostico.append(
                f"Erro ao interpretar linha: {erro}"
            )

    texto_final = "\n".join(
        linhas
    )

    diagnostico_final = "\n".join(
        diagnostico
    )

    return (
        texto_final,
        diagnostico_final
    )


# ============================================================
# 8. LER DOCUMENTO
# ============================================================

def ler_documento(arquivo):

    nome = arquivo.name.lower()

    textos = []

    diagnosticos = []


    if nome.endswith(".pdf"):

        imagens = pdf_para_imagens(
            arquivo
        )

        for numero_pagina, imagem in enumerate(
            imagens,
            start=1
        ):

            texto, diagnostico = (
                executar_ocr_imagem(
                    imagem
                )
            )

            if texto:
                textos.append(
                    texto
                )

            diagnosticos.append(
                f"===== PÁGINA {numero_pagina} =====\n"
                f"{diagnostico}"
            )


    else:

        arquivo.seek(0)

        imagem = Image.open(
            arquivo
        )

        texto, diagnostico = (
            executar_ocr_imagem(
                imagem
            )
        )

        if texto:
            textos.append(
                texto
            )

        diagnosticos.append(
            diagnostico
        )


    return (
        "\n".join(textos),
        "\n\n".join(diagnosticos)
    )


# ============================================================
# 9. FUNÇÕES AUXILIARES
# ============================================================

def somente_numeros(valor):

    return re.sub(
        r"\D",
        "",
        str(valor or "")
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


def formatar_titulo(titulo):

    titulo = somente_numeros(
        titulo
    )

    return titulo


# ============================================================
# 10. EXTRAIR DADOS DO TEXTO
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

    padroes_cpf = [

        r"\b\d{3}\s*[.\-]?\s*\d{3}\s*[.\-]?\s*\d{3}\s*[-.]?\s*\d{2}\b",

        r"(?:CPF)[^\d]{0,20}(\d[\d\s.\-]{8,16}\d)"
    ]


    for padrao in padroes_cpf:

        match = re.search(
            padrao,
            texto,
            flags=re.IGNORECASE
        )

        if match:

            valor = (
                match.group(1)
                if match.lastindex
                else match.group(0)
            )

            cpf = somente_numeros(
                valor
            )

            if len(cpf) == 11:

                dados["cpf"] = (
                    formatar_cpf(
                        cpf
                    )
                )

                break


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

                dados["titulo"] = (
                    formatar_titulo(
                        numero
                    )
                )

                break


    # --------------------------------------------------------
    # NASCIMENTO
    # --------------------------------------------------------

    padroes_nascimento = [

        r"(?:DATA\s+DE\s+NASCIMENTO|NASCIMENTO|NASC)[^\d]{0,30}(\d{2}\s*[\/.\-]\s*\d{2}\s*[\/.\-]\s*\d{4})",

        r"\b(\d{2}\s*[\/.\-]\s*\d{2}\s*[\/.\-]\s*\d{4})\b"
    ]


    for padrao in padroes_nascimento:

        match = re.search(
            padrao,
            texto,
            flags=re.IGNORECASE
        )

        if match:

            valor = re.sub(
                r"\s",
                "",
                match.group(1)
            )

            dados["data_nascimento"] = (
                valor
                .replace(".", "/")
                .replace("-", "/")
            )

            break


    # --------------------------------------------------------
    # ZONA
    # --------------------------------------------------------

    zona_match = re.search(
        r"\bZONA\b[^\d]{0,20}(\d{1,3})",
        texto,
        flags=re.IGNORECASE
    )

    if zona_match:

        dados["zona"] = (
            zona_match.group(1)
        )


    # --------------------------------------------------------
    # SEÇÃO
    # --------------------------------------------------------

    secao_match = re.search(
        r"\bSE[ÇC][ÃA]O\b[^\d]{0,20}(\d{1,4})",
        texto,
        flags=re.IGNORECASE
    )

    if secao_match:

        dados["secao"] = (
            secao_match.group(1)
        )


    # --------------------------------------------------------
    # NOME
    # --------------------------------------------------------

    linhas = [
        linha.strip()
        for linha in texto.splitlines()
        if linha.strip()
    ]


    palavras_ignorar = [
        "REPÚBLICA",
        "REPUBLICA",
        "BRASIL",
        "JUSTIÇA",
        "JUSTICA",
        "ELEITORAL",
        "TÍTULO",
        "TITULO",
        "CPF",
        "NASCIMENTO",
        "ZONA",
        "SEÇÃO",
        "SECAO",
        "INSCRIÇÃO",
        "INSCRICAO"
    ]


    # Primeiro procura indicação explícita de nome
    for i, linha in enumerate(
        linhas
    ):

        linha_upper = (
            linha.upper()
        )

        if (
            "NOME DO ELEITOR"
            in linha_upper
            or linha_upper == "NOME"
        ):

            if i + 1 < len(linhas):

                candidato = (
                    linhas[i + 1]
                    .strip()
                )

                if len(candidato) >= 5:

                    dados["nome"] = (
                        candidato.upper()
                    )

                    break


    # Segunda tentativa:
    # procura linha que pareça nome completo
    if not dados["nome"]:

        candidatos = []

        for linha in linhas:

            linha_limpa = (
                linha.strip()
            )

            linha_upper = (
                linha_limpa.upper()
            )

            if any(
                palavra in linha_upper
                for palavra
                in palavras_ignorar
            ):
                continue

            if re.search(
                r"\d",
                linha_limpa
            ):
                continue

            palavras = (
                linha_limpa.split()
            )

            if (
                2 <= len(palavras) <= 7
                and len(linha_limpa) >= 8
            ):

                letras = re.sub(
                    r"[^A-Za-zÀ-ÿ]",
                    "",
                    linha_limpa
                )

                if len(letras) >= 7:

                    candidatos.append(
                        linha_limpa
                    )


        if candidatos:

            dados["nome"] = (
                max(
                    candidatos,
                    key=len
                ).upper()
            )


    return dados


# ============================================================
# 11. CARREGAR SUPERVISORES
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
# 12. CABEÇALHO
# ============================================================

st.title(
    "📋 Sistema de Cadastro CP"
)

st.markdown("---")


# ============================================================
# 13. SIDEBAR
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
# 14. ENVIO DE DOCUMENTOS
# ============================================================

if menu == "📸 Envio de Documentos":

    st.markdown(
        f"#### 📁 Leitura Automática — "
        f"**Sup:** {supervisor} | "
        f"**Sub:** {sub}"
    )


    st.info(
        "💡 Teste de leitura com EasyOCR. "
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


                # ============================================
                # PREVIEW
                # ============================================

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

                        imagem_preview = (
                            ImageOps.exif_transpose(
                                imagem_preview
                            )
                        )

                        st.image(
                            imagem_preview,
                            caption="Documento enviado",
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

                        dados = (
                            extrair_dados(
                                texto
                            )
                        )


                    # ========================================
                    # TEXTO OCR
                    # ========================================

                    st.markdown(
                        "### 📝 Texto reconhecido"
                    )


                    if texto:

                        st.success(
                            "Texto encontrado no documento."
                        )

                        st.text_area(
                            "Resultado da leitura",
                            texto,
                            height=300,
                            key=f"ocr_{i}"
                        )

                    else:

                        st.warning(
                            "Nenhum texto foi reconhecido."
                        )


                    # ========================================
                    # DADOS
                    # ========================================

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
                                "Nenhuma linha "
                                "reconhecida."
                            )


                except Exception as ex:

                    st.error(
                        f"Erro ao processar "
                        f"{arquivo.name}: {ex}"
                    )

                    st.exception(
                        ex
                    )


                barra.progress(
                    (i + 1) / total
                )


# ============================================================
# 15. FORMULÁRIO MANUAL
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
                                f"Erro ao salvar: {ex}"
                            )
