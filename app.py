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
    div.stButton > button { background-color: #0056b3 !important; color: white !important; border-radius: 15px !important; border: 2px solid #0056b3 !important; font-weight: bold !important; }
    </style>
""", unsafe_allow_html=True)

try:
    WEBHOOK_URL = st.secrets["WEBHOOK_URL"]
except Exception as e:
    st.error("Erro nas chaves de segurança (Secrets).")
    st.stop()

st.title("🗳️ Sistema de Cadastro CP")
st.markdown("---")

@st.cache_data(ttl=600)
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
    st.markdown(f"#### 📁 Envio e Leitura Automática — **Sup:** {supervisor} | **Sub:** {sub}")
    arquivos = st.file_uploader("Arraste fotos/PDFs", accept_multiple_files=True, type=['pdf', 'jpg', 'png'])
    
    if arquivos and st.button("🚀 Processar e Cadastrar Lote"):
        barra = st.progress(0)
        total = len(arquivos)
        sucessos, duplicados = 0, 0
        
        for i, arquivo in enumerate(arquivos):
            try:
                # Aqui o arquivo é enviado e o Apps Script fará o OCR
                files = {'file': (arquivo.name, arquivo.getvalue())}
                data = {'supervisor': supervisor, 'subsupervisor': sub}
                
                res = requests.post(WEBHOOK_URL, files=files, data=data, timeout=30)
                
                if res.status_code == 200:
                    res_json = res.json()
                    if res_json.get("status") == "SUCESSO":
                        sucessos += 1
                        st.success(f"✅ {arquivo.name}: Cadastrado!")
                    else:
                        duplicados += 1
                        st.warning(f"⚠️ {arquivo.name}: {res_json.get('mensagem')}")
                else:
                    st.error(f"Erro no envio de {arquivo.name}")
            except Exception as ex:
                st.error(f"Erro: {ex}")
            barra.progress((i + 1) / total)

elif menu == "✍️ Formulário Manual":
    # (Mantive a lógica original do formulário)
    st.subheader("✍️ Consulta & Cadastro Manual")
    titulo_input = st.text_input("Título de Eleitor")
    if st.button("🔍 Pesquisar"):
        try:
            dados_base = requests.get(WEBHOOK_URL, timeout=5).json()
            encontrado = next((r for r in dados_base if re.sub(r'\D', '', str(r.get("titulo", ""))).lstrip('0') == re.sub(r'\D', '', titulo_input).lstrip('0')), None)
            if encontrado:
                st.error(f"⚠️ Já cadastrado: {encontrado.get('nome')}")
            else:
                with st.form("manual"):
                    nome = st.text_input("Nome *")
                    if st.form_submit_button("💾 Salvar"):
                        requests.post(WEBHOOK_URL, json={"titulo": titulo_input, "nome": nome, "supervisor": supervisor, "subsupervisor": sub})
                        st.success("Salvo!")
        except: st.error("Erro na busca.")
