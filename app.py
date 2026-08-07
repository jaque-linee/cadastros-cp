import streamlit as st
import requests
from google import genai
from google.genai import types
import json

# Configuração da página
st.set_page_config(page_title="Sistema de Cadastro CP", layout="centered", page_icon="🗳️")

# Lendo as chaves do cofre de segurança (Secrets)
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    WEBHOOK_URL = st.secrets["WEBHOOK_URL"]
except Exception as e:
    st.error("Erro: As chaves de segurança (Secrets) não foram configuradas corretamente no Streamlit.")
    st.stop()

# Inicializa o cliente do Gemini
client = genai.Client(api_key=API_KEY)

st.title("🗳️ Sistema de Cadastro CP")
st.markdown("---")

# Gerenciamento de Supervisores na sessão do Streamlit para permitir cadastrar novos
if 'lista_supervisores' not in st.session_state:
    st.session_state.lista_supervisores = ["ADEILTON", "ADRIANO BATISTA", "TESTE"]

if 'lista_subs' not in st.session_state:
    st.session_state.lista_subs = ["SEM SUBSUPERVISOR"]

# Barra Lateral para configuração e menus
with st.sidebar:
    st.header("⚙️ Configuração")
    
    # Seleção ou Cadastro de Supervisor
    sup_opcao = st.selectbox("Supervisor", st.session_state.lista_supervisores + ["➕ Cadastrar Novo Supervisor"])
    if sup_opcao == "➕ Cadastrar Novo Supervisor":
        novo_sup = st.text_input("Nome do Novo Supervisor").upper()
        if st.button("Salvar Supervisor") and novo_sup:
            if novo_sup not in st.session_state.lista_supervisores:
                st.session_state.lista_supervisores.append(novo_sup)
                st.success(f"Supervisor {novo_sup} cadastrado!")
                st.rerun()
        supervisor = novo_sup if novo_sup else "INDEFINIDO"
    else:
        supervisor = sup_opcao

    # Seleção ou Cadastro de Subsupervisor
    sub_opcao = st.selectbox("Subsupervisor", st.session_state.lista_subs + ["➕ Cadastrar Novo Sub"])
    if sub_opcao == "➕ Cadastrar Novo Sub":
        novo_sub = st.text_input("Nome do Novo Subsupervisor").upper()
        if st.button("Salvar Sub") and novo_sub:
            if novo_sub not in st.session_state.lista_subs:
                st.session_state.lista_subs.append(novo_sub)
                st.success(f"Subsupervisor {novo_sub} cadastrado!")
                st.rerun()
        sub = novo_sub if novo_sub else "SEM SUBSUPERVISOR"
    else:
        sub = sub_opcao

    st.markdown("---")
    menu = st.radio("Escolha a Operação:", ["📸 Envio de Documentos", "✍️ Formulário Manual"])

# Corpo Principal baseado na escolha do menu
if menu == "📸 Envio de Documentos":
    st.subheader(f"📁 Envio de Documentos - Sup: {supervisor} / Sub: {sub}")
    arquivos = st.file_uploader("Arraste ou escolha as fotos/PDFs", accept_multiple_files=True, type=['pdf', 'jpg', 'png'])
    
    if arquivos:
        if st.button("Processar Lote"):
            barra_progresso = st.progress(0)
            total = len(arquivos)
            sucessos = 0
            
            for i, arquivo in enumerate(arquivos):
                bytes_dados = arquivo.getvalue()
                mime_type = "application/pdf" if arquivo.type == "application/pdf" else "image/jpeg"
                
                prompt_extracao = """
                Analise este documento e extraia os dados em formato JSON puro contendo exatamente estas chaves:
                - titulo_eleitor
                - nome
                - cpf
                - data_nascimento
                - zona
                - secao
                Retorne apenas o JSON válido, sem markdown extra.
                """
                
                try:
                    resposta = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[
                            types.Part.from_bytes(data=bytes_dados, mime_type=mime_type),
                            prompt_extracao
                        ]
                    )
                    
                    texto_resposta = resposta.text.replace("```json", "").replace("```", "").strip()
                    dados_extraidos = json.loads(texto_resposta)
                    dados_extraidos["supervisor"] = supervisor
                    dados_extraidos["subsupervisor"] = sub
                    
                    response_webhook = requests.post(WEBHOOK_URL, json=dados_extraidos)
                    if response_webhook.status_code == 200:
                        sucessos += 1
                except Exception as e:
                    pass
                
                barra_progresso.progress((i + 1) / total)
            
            st.success(f"Processamento concluído! {sucessos} de {total} arquivo(s) salvos com sucesso.")

elif menu == "✍️ Formulário Manual":
    st.subheader(f"✍️ Cadastro Manual - Sup: {supervisor} / Sub: {sub}")
    titulo = st.text_input("Título de Eleitor")
    nome = st.text_input("Nome Completo")
    cpf = st.text_input("CPF")
    
    if st.button("Salvar Cadastro Manual"):
        if titulo and nome:
            payload = {
                "titulo_eleitor": titulo,
                "nome": nome,
                "cpf": cpf,
                "supervisor": supervisor,
                "subsupervisor": sub
            }
            try:
                res = requests.post(WEBHOOK_URL, json=payload)
                if res.status_code == 200:
                    st.success("Cadastro manual salvo com sucesso!")
                else:
                    st.error("Erro ao enviar para a planilha.")
            except Exception as e:
                st.error(f"Erro de conexão: {e}")
        else:
            st.warning("Preencha ao menos o Título de Eleitor e o Nome.")
