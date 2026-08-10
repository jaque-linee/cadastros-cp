import streamlit as st
import requests
from google import genai
from google.genai import types
import json
import re

# 1. Configuração da página
st.set_page_config(page_title="Sistema de Cadastro CP", layout="centered", page_icon="🗳️")

# 2. CSS "Força Bruta"
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
    API_KEY = st.secrets["GEMINI_API_KEY"]
    WEBHOOK_URL = st.secrets["WEBHOOK_URL"]
except Exception as e:
    st.error("Erro nas chaves de segurança (Secrets) do Streamlit.")
    st.stop()

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
    st.markdown(f"#### 📁 Envio e Leitura Automática — **Sup:** {supervisor} | **Sub:** {sub}")
    st.info("💡 Envie fotos ou PDFs. A IA vai ler os dados e verificar duplicidade automaticamente.")
    
    arquivos = st.file_uploader("Arraste ou escolha as fotos/PDFs", accept_multiple_files=True, type=['pdf', 'jpg', 'png'])
    
    if arquivos and st.button("🚀 Processar e Cadastrar Lote"):
        barra = st.progress(0)
        total = len(arquivos)
        sucessos, duplicados = 0, 0
        try:
            res_base = requests.get(WEBHOOK_URL, timeout=5)
            dados_base = res_base.json() if res_base.status_code == 200 else []
        except:
            dados_base = []

        for i, arquivo in enumerate(arquivos):
            bytes_dados = arquivo.getvalue()
            mime_type = "application/pdf" if arquivo.type == "application/pdf" else "image/jpeg"
            prompt = "Extraia dados do documento em JSON puro: titulo, nome, cpf, data_nascimento, zona, secao, rg, nome_mae, endereco, numero, bairro, cidade, comunidade, domicilio, telefone, nis, dap, sus. Retorne apenas o JSON."
            
            try:
                # Modelo corrigido para gemini-2.0-flash
                resposta = client.models.generate_content(model='gemini-2.0-flash', contents=[types.Part.from_bytes(data=bytes_dados, mime_type=mime_type), prompt])
                texto = resposta.text.replace("```json", "").replace("```", "").strip()
                dados = json.loads(texto)
                titulo_limpo = re.sub(r'\D', '', str(dados.get("titulo", ""))).lstrip('0')
                st.write(f"🔍 Título lido: **{titulo_limpo if titulo_limpo else 'Não identificado'}**")
                
                if titulo_limpo:
                    ja_existe = any(re.sub(r'\D', '', str(r.get("titulo", ""))).lstrip('0') == titulo_limpo for r in dados_base)
                    if not ja_existe:
                        dados.update({"titulo": titulo_limpo, "supervisor": supervisor, "subsupervisor": sub})
                        if requests.post(WEBHOOK_URL, json=dados).status_code == 200:
                            sucessos += 1
                    else:
                        duplicados += 1
                        st.warning(f"⚠️ O título {titulo_limpo} já consta na base.")
            except Exception as ex:
                st.error(f"Erro no processamento: {ex}")
            barra.progress((i + 1) / total)
        st.success(f"✨ Processamento concluído! {sucessos} novos cadastros.")
        if duplicados > 0: st.warning(f"⚠️ {duplicados} ignorados por duplicidade.")

elif menu == "✍️ Formulário Manual":
    st.subheader(f"✍️ Consulta & Cadastro Manual - Sup: {supervisor} / Sub: {sub}")
    if "busca_realizada" not in st.session_state: st.session_state.update({"busca_realizada": False, "titulo_pesquisado": "", "eleitor_encontrado": None})
    
    col_busca, col_btn = st.columns([3, 1])
    with col_busca: titulo_input = st.text_input("Título de Eleitor para consultar:", value=st.session_state.titulo_pesquisado)
    with col_btn: 
        st.write("")
        st.write("")
        btn_buscar = st.button("🔍 Pesquisar")

    if btn_buscar:
        titulo_limpo = re.sub(r'\D', '', titulo_input).lstrip('0')
        if not titulo_limpo: st.warning("Informe um Título válido.")
        else:
            st.session_state.titulo_pesquisado = titulo_input
            st.session_state.busca_realizada = True
            try:
                dados_base = requests.get(WEBHOOK_URL, timeout=5).json()
                st.session_state.eleitor_encontrado = next((r for r in dados_base if re.sub(r'\D', '', str(r.get("titulo", ""))).lstrip('0') == titulo_limpo), None)
            except: dados_base = []

    if st.session_state.busca_realizada:
        if st.session_state.eleitor_encontrado:
            st.error("⚠️ Título já cadastrado na base!")
            e = st.session_state.eleitor_encontrado
            st.info(f"**Nome:** {e.get('nome')} | **CPF:** {e.get('cpf')} | **Sup:** {e.get('supervisor')}")
            if st.button("🔄 Consultar Outro Título"): st.session_state.update({"busca_realizada": False, "titulo_pesquisado": "", "eleitor_encontrado": None}); st.rerun()
        else:
            st.success("✅ Título não encontrado. Preencha os campos abaixo:")
            with st.form("form_cadastro_manual_completo", clear_on_submit=True):
                st.text_input("Título de Eleitor", value=st.session_state.titulo_pesquisado, disabled=True)
                nome_f = st.text_input("Nome Completo *")
                cpf_f = st.text_input("CPF")
                rg_f = st.text_input("RG")
                data_nasc_f = st.text_input("Data de Nascimento (DD/MM/AAAA)")
                nome_mae_f = st.text_input("Nome da Mãe")
                endereco_f = st.text_input("Endereço")
                numero_f = st.text_input("Nº")
                bairro_f = st.text_input("Bairro")
                cidade_f = st.text_input("Cidade")
                zona_f = st.text_input("Zona")
                secao_f = st.text_input("Seção")
                comunidade_f = st.text_input("Comunidade")
                domicilio_f = st.text_input("Domicílio (Ex: R)")
                telefone_f = st.text_input("Telefone")
                nis_f = st.text_input("NIS")
                dap_f = st.text_input("DAP")
                sus_f = st.text_input("SUS")
                
                if st.form_submit_button("💾 Salvar Cadastro Completo"):
                    if not nome_f:
                        st.error("O campo Nome Completo é obrigatório.")
                    else:
                        data_limpa = re.sub(r'\D', '', data_nasc_f)
                        data_formatada = f"{data_limpa[:2]}/{data_limpa[2:4]}/{data_limpa[4:]}" if len(data_limpa) == 8 else data_nasc_f
                        payload = {
                            "titulo": st.session_state.titulo_pesquisado, "nome": nome_f, "cpf": cpf_f, "rg": rg_f,
                            "data_nascimento": data_formatada, "nome_mae": nome_mae_f, "endereco": endereco_f,
                            "numero": numero_f, "bairro": bairro_f, "cidade": cidade_f, "zona": zona_f,
                            "secao": secao_f, "comunidade": comunidade_f, "domicilio": domicilio_f,
                            "telefone": telefone_f, "nis": nis_f, "dap": dap_f, "sus": sus_f,
                            "supervisor": supervisor, "subsupervisor": sub
                        }
                        try:
                            res = requests.post(WEBHOOK_URL, json=payload)
                            if res.status_code == 200 and res.json().get("status") == "SUCESSO":
                                st.success("🎉 Cadastro realizado com sucesso!")
                                st.session_state.update({"busca_realizada": False, "titulo_pesquisado": "", "eleitor_encontrado": None})
                                st.rerun()
                            else:
                                st.warning("Erro ao salvar na planilha.")
                        except Exception as ex:
                            st.error(f"Erro ao salvar: {ex}")
