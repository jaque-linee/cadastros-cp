import streamlit as st
import requests
import json
import re

# 1. Configuração da página
st.set_page_config(page_title="Sistema de Cadastro CP", layout="centered", page_icon="🗳️")

# 2. CSS
st.markdown("""
    <style>
    .stApp { background-color: #eef2f5 !important; }
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
    WEBHOOK_URL = st.secrets["WEBHOOK_URL"]
except Exception as e:
    st.error("Erro na configuração do Webhook.")
    st.stop()

st.title("🗳️ Sistema de Cadastro CP")
st.markdown("---")

# Função de busca rápida (agora apenas via Webhook)
def carregar_supervisores_rapido():
    supervisores_encontrados = ["ADEILTON", "ADRIANO BATISTA", "TESTE"]
    subs_encontrados = ["SEM SUBSUPERVISOR"]
    try:
        response = requests.get(WEBHOOK_URL, timeout=5)
        if response.status_code == 200:
            for item in response.json():
                sup = str(item.get("supervisor", "")).strip().upper()
                sub = str(item.get("subsupervisor", "")).strip().upper()
                if sup and sup not in supervisores_encontrados: supervisores_encontrados.append(sup)
                if sub and sub not in subs_encontrados: subs_encontrados.append(sub)
    except: pass
    return sorted(supervisores_encontrados), sorted(subs_encontrados)

lista_sup, lista_sub = carregar_supervisores_rapido()

with st.sidebar:
    st.header("⚙️ Configuração")
    sup_opcao = st.selectbox("Supervisor", lista_sup + ["➕ Cadastrar Novo Supervisor"])
    supervisor = st.text_input("Novo Supervisor").upper() if sup_opcao == "➕ Cadastrar Novo Supervisor" else sup_opcao
    sub_opcao = st.selectbox("Subsupervisor", lista_sub + ["➕ Cadastrar Novo Sub"])
    sub = st.text_input("Novo Sub").upper() if sub_opcao == "➕ Cadastrar Novo Sub" else sub_opcao
    st.markdown("---")
    menu = st.radio("Escolha a Operação:", ["📸 Envio de Documentos", "✍️ Formulário Manual"])

if menu == "📸 Envio de Documentos":
    st.markdown(f"#### 📁 Envio — **Sup:** {supervisor} | **Sub:** {sub}")
    st.info("💡 Suba o documento. O sistema enviará para processamento automático no Drive.")
    
    arquivos = st.file_uploader("Arraste as fotos", accept_multiple_files=True, type=['pdf', 'jpg', 'png'])
    
    if arquivos and st.button("🚀 Enviar para Processamento"):
        for arquivo in arquivos:
            # Aqui ele envia o arquivo para o seu Webhook (Apps Script)
            # O Apps Script agora cuida do OCR e da validação
            files = {'file': (arquivo.name, arquivo.getvalue())}
            data = {'supervisor': supervisor, 'subsupervisor': sub}
            res = requests.post(WEBHOOK_URL, files=files, data=data)
            st.success(f"Arquivo {arquivo.name} enviado para processamento!")

elif menu == "✍️ Formulário Manual":
    # ... (mantenha a lógica do seu formulário manual, está perfeita!)
    # Apenas certifique-se de que os nomes dos campos no payload 
    # coincidam com o que o seu Script no Google Sheets espera.
