import streamlit as st
import requests
from google import genai
from google.genai import types
import json
import re

# 1. Configuração da página
st.set_page_config(page_title="Sistema de Cadastro CP", layout="centered", page_icon="🗳️")

# 2. CSS "Força Bruta" para testar o layout
st.markdown("""
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
""", unsafe_allow_html=True)

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    WEBHOOK_URL = st.secrets["WEBHOOK_URL"]
except Exception as e:
    st.error("Erro nas chaves de segurança (Secrets) do Streamlit.")
    st.stop()

# Cliente inicializado na ordem correta
client = genai.Client(api_key=API_KEY)

st.title("🗳️ Sistema de Cadastro CP")
st.markdown("---")

@st.cache_data(ttl=600)
def carregar_supervisores_rapido():
    supervisores_encontrados = ["ADEILTON", "ADRIANO BATISTA", "TESTE"]
    subs_encontrados = ["SEM SUBSUPERVISOR"]
    try:
        response = requests.get(WEBHOOK_URL, timeout=3)
        if response.status_code == 200:
            for item in response.json():
                sup = str(item.get("supervisor", "")).strip().upper()
                sub = str(item.get("subsupervisor", "")).strip().upper()
                if sup and sup not in supervisores_encontrados:
                    supervisores_encontrados.append(sup)
                if sub and sub not in subs_encontrados:
                    subs_encontrados.append(sub)
    except Exception:
        pass
    return sorted(supervisores_encontrados), sorted(subs_encontrados)

lista_sup, lista_sub = carregar_supervisores_rapido()

with st.sidebar:
    st.header("⚙️ Configuração")
    
    sup_opcao = st.selectbox("Supervisor", lista_sup + ["➕ Cadastrar Novo Supervisor"])
    if sup_opcao == "➕ Cadastrar Novo Supervisor":
        novo_sup = st.text_input("Nome do Novo Supervisor").upper()
        supervisor = novo_sup if novo_sup else "INDEFINIDO"
    else:
        supervisor = sup_opcao

    sub_opcao = st.selectbox("Subsupervisor", lista_sub + ["➕ Cadastrar Novo Sub"])
    if sub_opcao == "➕ Cadastrar Novo Sub":
        novo_sub = st.text_input("Nome do Novo Subsupervisor").upper()
        sub = novo_sub if novo_sub else "SEM SUBSUPERVISOR"
    else:
        sub = sub_opcao

    st.markdown("---")
    menu = st.radio("Escolha a Operação:", ["📸 Envio de Documentos", "✍️ Formulário Manual"])

if menu == "📸 Envio de Documentos":
    st.subheader(f"📁 Envio - Sup: {supervisor} / Sub: {sub}")
    arquivos = st.file_uploader("Arraste ou escolha as fotos/PDFs", accept_multiple_files=True, type=['pdf', 'jpg', 'png'])
    
    if arquivos:
        if st.button("Processar Lote"):
            barra = st.progress(0)
            total = len(arquivos)
            sucessos = 0
            
            for i, arquivo in enumerate(arquivos):
                bytes_dados = arquivo.getvalue()
                mime_type = "application/pdf" if arquivo.type == "application/pdf" else "image/jpeg"
                
                prompt = """
                Analise este documento e extraia os dados em formato JSON puro contendo exatamente estas chaves:
                - titulo
                - nome
                - cpf
                - data_nascimento
                - zona
                - secao
                - rg
                - nome_mae
                - endereco
                - numero
                - bairro
                - cidade
                - comunidade
                - domicilio
                - telefone
                - nis
                - dap
                - sus
                Retorne apenas o JSON válido, sem markdown extra.
                """
                
                try:
                    resposta = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[types.Part.from_bytes(data=bytes_dados, mime_type=mime_type), prompt]
                    )
                    texto = resposta.text.replace("```json", "").replace("
