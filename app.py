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
    st.error("Erro nas chaves de segurança (Secrets) do Streamlit.")
    st.stop()

st.title("🗳️ Sistema de Cadastro CP")
st.markdown("---")

@st.cache_data(ttl=60)
def carregar_supervisores_rapido():
    supervisores_encontrados = []
    subs_encontrados = ["SEM SUBSUPERVISOR"]
    try:
        response = requests.get(WEBHOOK_URL, timeout=8)
        if response.status_code == 200:
            dados = response.json()
            if isinstance(dados, list):
                for item in dados:
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
    supervisor = st.text_input("Novo Supervisor").upper() if sup_opcao == "➕ Cadastrar Novo Supervisor" else sup_opcao
    
    sub_opcao = st.selectbox("Subsupervisor", lista_sub + ["➕ Cadastrar Novo Sub"])
    sub = st.text_input("Novo Sub").upper() if sub_opcao == "➕ Cadastrar Novo Sub" else sub_opcao
    
    st.markdown("---")
    menu = st.radio("Escolha a Operação:", ["📸 Envio de Documentos", "✍️ Formulário Manual"])

if menu == "📸 Envio de Documentos":
    st.markdown(f"#### 📁 Envio e Leitura Automática — **Sup:** {supervisor} | **Sub:** {sub}")
    st.info("💡 Envie fotos ou PDFs dos documentos.")
    
    arquivos = st.file_uploader("Arraste fotos/PDFs", accept_multiple_files=True, type=['pdf', 'jpg', 'png'])
    
    if arquivos:
        if st.button("🚀 Processar e Cadastrar Lote"):
            barra = st.progress(0)
            total = len(arquivos)
            sucessos, duplicados = 0, 0
            
            for i, arquivo in enumerate(arquivos):
                try:
                    payload = {
                        "supervisor": supervisor,
                        "subsupervisor": sub,
                        "nome": f"DOCUMENTO - {arquivo.name}",
                        "titulo": "",
                        "cpf": "",
                        "data_nascimento": "",
                        "cidade": "ARAPIRACA"
                    }
                    
                    res = requests.post(WEBHOOK_URL, json=payload, timeout=30)
                    
                    if res.status_code == 200:
                        res_json = res.json()
                        if res_json.get("status") == "SUCESSO":
                            sucessos += 1
                            st.success(f"✅ {arquivo.name}: Cadastrado com sucesso!")
                        else:
                            duplicados += 1
                            st.warning(f"⚠️ {arquivo.name}: {res_json.get('mensagem', 'Duplicado.')}")
                    else:
                        st.error(f"Erro ao enviar {arquivo.name}")
                except Exception as ex:
                    st.error(f"Erro no arquivo {arquivo.name}: {ex}")
                    
                barra.progress((i + 1) / total)
                
            st.markdown(f"**Resumo do Lote:** 🟢 **{sucessos}** salvos | 🟡 **{duplicados}** duplicados ignorados.")

elif menu == "✍️ Formulário Manual":
    st.subheader("✍️ Consulta & Cadastro Manual")
    if "busca_realizada" not in st.session_state: 
        st.session_state.update({"busca_realizada": False, "titulo": "", "encontrado": None})
    
    titulo_input = st.text_input("Título de Eleitor:", value=st.session_state.titulo)
    if st.button("🔍 Pesquisar"):
        st.session_state.titulo = titulo_input
        st.session_state.busca_realizada = True
        try:
            dados_base = requests.get(WEBHOOK_URL, timeout=5).json()
            st.session_state.encontrado = next((r for r in dados_base if re.sub(r'\D', '', str(r.get("titulo", ""))).lstrip('0') == re.sub(r'\D', '', titulo_input).lstrip('0')), None)
        except: 
            st.session_state.encontrado = None

    if st.session_state.busca_realizada:
        if st.session_state.encontrado:
            e = st.session_state.encontrado
            st.error(f"⚠️ Já cadastrado: {e.get('nome')} | Sup: {e.get('supervisor')}")
            if st.button("Limpar"): 
                st.session_state.busca_realizada = False
                st.rerun()
        else:
            with st.form("cadastro_manual"):
                nome = st.text_input("Nome *")
                cpf = st.text_input("CPF")
                data_nasc = st.text_input("Data de Nascimento (DD/MM/AAAA)")
                
                if st.form_submit_button("💾 Salvar"):
                    if nome:
                        payload = {
                            "titulo": st.session_state.titulo,
                            "nome": nome,
                            "cpf": cpf,
                            "data_nascimento": data_nasc,
                            "supervisor": supervisor,
                            "subsupervisor": sub
                        }
                        requests.post(WEBHOOK_URL, json=payload)
                        st.success("Salvo com sucesso!")
                        st.session_state.busca_realizada = False
                        st.rerun()
