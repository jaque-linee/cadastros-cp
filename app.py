import streamlit as st
import requests
from google import genai

# Configuração da página
st.set_page_config(page_title="Sistema de Cadastro CP", layout="centered", page_icon="🗳️")

# Lendo as chaves do cofre de segurança (Secrets) do Streamlit
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    WEBHOOK_URL = st.secrets["WEBHOOK_URL"]
except Exception as e:
    st.error("Erro: As chaves de segurança (Secrets) não foram configuradas corretamente no Streamlit.")
    st.stop()

st.title("🗳️ Sistema de Cadastro CP")
st.markdown("---")

# Menu Lateral
menu = st.sidebar.radio("Escolha a Operação:", ["📸 Envio de Documentos", "✍️ Formulário Manual"])

# Seletor de Supervisor/Sub
col1, col2 = st.columns(2)
with col1:
    supervisor = st.selectbox("Supervisor", ["ADEILTON", "ADRIANO BATISTA", "TESTE"])
with col2:
    sub = st.text_input("Subsupervisor", "SEM SUBSUPERVISOR")

st.markdown("---")

if menu == "📸 Envio de Documentos":
    st.subheader("Upload de Documentos")
    arquivos = st.file_uploader("Arraste ou escolha as fotos/PDFs", accept_multiple_files=True, type=['pdf', 'jpg', 'png'])
    
    if arquivos:
        if st.button("Processar Lote"):
            st.info(f"{len(arquivos)} arquivo(s) pronto(s) para processamento com o Gemini.")
            # Aqui depois colocaremos a lógica de envio para o Gemini e Webhook

elif menu == "✍️ Formulário Manual":
    st.subheader("Cadastro Manual")
    titulo = st.text_input("Título de Eleitor")
    nome = st.text_input("Nome Completo")
    
    if st.button("Salvar Cadastro"):
        if titulo and nome:
            st.success("Dados preenchidos com sucesso!")
        else:
            st.warning("Preencha todos os campos obrigatórios.")
