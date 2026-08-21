import streamlit as st
import requests
import re
from tela_relatorios import exibir_tela_relatorios
from tela_formulario_manual import exibir_tela_formulario_manual
from tela_envio_documentos import exibir_tela_envio_documentos
from validacoes import (
    somente_numeros,
    normalizar_texto,
    remover_acentos,
    normalizar_rotulo,
    formatar_cpf,
    cpf_valido,
    data_valida,
)


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


from processamento_documentos import (
    ler_documento,
    extrair_dados,
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
#
# Nome
# + nascimento
# + nome da mãe
# + CPF OU título
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

    comunidades = []

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

        comunidade = str(
            item.get(
                "comunidade",
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

        if (
            comunidade
            and comunidade not in comunidades
        ):
            comunidades.append(
                comunidade
            )

    return (
        sorted(
            supervisores
        ),
        sorted(
            subs
        ),
        sorted(
            comunidades
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

lista_sup, lista_sub, lista_comunidade = obter_supervisores(
    base
)


# ============================================================
# 32. SIDEBAR
# ============================================================

with st.sidebar:
    st.header(
        "⚙️ Menu"
    )

    menu = st.radio(
        "Escolha a Operação:",
        [
            "📸 Envio de Documentos",
            "✍️ Formulário Manual",
            "📊 Relatórios"
        ]
    )

    supervisor = ""
    sub = ""
    comunidade = ""

    if menu != "📊 Relatórios":
        st.markdown(
            "---"
        )

        st.subheader(
            "Configuração do cadastro"
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
            ).strip().upper()
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
            ).strip().upper()
        else:
            sub = sub_opcao

        comunidade_opcao = st.selectbox(
            "Comunidade",
            lista_comunidade
            + [
                "➕ Cadastrar Nova Comunidade"
            ]
        )

        if (
            comunidade_opcao
            == "➕ Cadastrar Nova Comunidade"
        ):
            comunidade = st.text_input(
                "Nova Comunidade"
            ).strip().upper()
        else:
            comunidade = comunidade_opcao

if menu == "📸 Envio de Documentos":
    exibir_tela_envio_documentos(
        base, supervisor, sub,
        ler_documento, extrair_dados,
        verificar_duplicidade, classificar_resultado,
        WEBHOOK_URL, comunidade
    )

elif menu == "✍️ Formulário Manual":
    exibir_tela_formulario_manual(base, WEBHOOK_URL, supervisor, sub)

elif menu == "📊 Relatórios":
    exibir_tela_relatorios(base)
