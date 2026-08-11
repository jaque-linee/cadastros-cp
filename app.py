import streamlit as st
import requests
import re

st.set_page_config(page_title="Sistema de Cadastro CP", layout="centered", page_icon="🗳️")

# Estilização
st.markdown("""
    <style>
    .stApp { background-color: #eef2f5 !important; }
    div.stButton > button { background-color: #0056b3 !important; color: white !important; border-radius: 15px !important; }
    </style>
""", unsafe_allow_html=True)

try:
    WEBHOOK_URL = st.secrets["WEBHOOK_URL"]
except:
    st.error("Erro nas configurações.")
    st.stop()

st.title("🗳️ Sistema de Cadastro CP")

# Sidebar
with st.sidebar:
    supervisor = st.text_input("Supervisor").upper()
    sub = st.text_input("Subsupervisor").upper()
    menu = st.radio("Operação:", ["📸 Envio de Documentos", "✍️ Formulário Manual"])

if menu == "📸 Envio de Documentos":
    st.markdown("### 📸 Leitura Automática")
    arquivos = st.file_uploader("Escolha as fotos/PDFs", accept_multiple_files=True, type=['pdf', 'jpg', 'png'])
    
    if arquivos and st.button("🚀 Processar e Cadastrar"):
        barra = st.progress(0)
        for i, arquivo in enumerate(arquivos):
            # Envia o arquivo cru para o Apps Script processar o OCR
            files = {'file': (arquivo.name, arquivo.getvalue())}
            data = {'supervisor': supervisor, 'subsupervisor': sub}
            
            res = requests.post(WEBHOOK_URL, files=files, data=data)
            
            if res.status_code == 200:
                res_json = res.json()
                if res_json.get("status") == "SUCESSO":
                    st.success(f"✅ {arquivo.name}: {res_json.get('mensagem')}")
                else:
                    st.warning(f"⚠️ {arquivo.name}: {res_json.get('mensagem')}")
            barra.progress((i + 1) / len(arquivos))

elif menu == "✍️ Formulário Manual":
    # (Mantém a lógica de busca manual que já funcionava bem)
    st.subheader("✍️ Cadastro Manual")
    titulo_manual = st.text_input("Título de Eleitor")
    if st.button("🔍 Salvar Manualmente"):
        payload = {"titulo": titulo_manual, "supervisor": supervisor, "subsupervisor": sub, "nome": "Manual"}
        requests.post(WEBHOOK_URL, json=payload)
        st.success("Salvo manualmente!")
