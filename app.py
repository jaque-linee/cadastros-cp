import streamlit as st
import requests
from google import genai
from google.genai import types
import json

st.set_page_config(page_title="Sistema de Cadastro CP", layout="centered", page_icon="🗳️")

try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    WEBHOOK_URL = st.secrets["WEBHOOK_URL"]
except Exception as e:
    st.error("Erro nas chaves de segurança (Secrets) do Streamlit.")
    st.stop()

client = genai.Client(api_key=API_KEY)

st.title("🗳️ Sistema de Cadastro CP")
st.markdown("---")

# Função de leitura sem cache para forçar a busca imediata
def buscar_supervisores_da_planilha():
    supervisores_encontrados = ["ADEILTON", "ADRIANO BATISTA", "TESTE"]
    subs_encontrados = ["SEM SUBSUPERVISOR"]
    try:
        response = requests.get(WEBHOOK_URL, timeout=10)
        if response.status_code == 200:
            dados = response.json()
            for item in dados:
                sup = str(item.get("supervisor", "")).strip().upper()
                sub = str(item.get("subsupervisor", "")).strip().upper()
                if sup and sup not in supervisores_encontrados:
                    supervisores_encontrados.append(sup)
                if sub and sub not in subs_encontrados:
                    subs_encontrados.append(sub)
        else:
            st.sidebar.warning(f"Status HTTP: {response.status_code}")
    except Exception as err:
        st.sidebar.error(f"Erro de conexão: {err}")
        
    return sorted(supervisores_encontrados), sorted(subs_encontrados)

lista_sup, lista_sub = buscar_supervisores_da_planilha()

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
                Retorne apenas o JSON válido, sem markdown extra.
                """
                
                try:
                    resposta = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[types.Part.from_bytes(data=bytes_dados, mime_type=mime_type), prompt]
                    )
                    texto = resposta.text.replace("```json", "").replace("```", "").strip()
                    dados = json.loads(texto)
                    
                    dados["supervisor"] = supervisor
                    dados["subsupervisor"] = sub
                    
                    res_web = requests.post(WEBHOOK_URL, json=dados)
                    if res_web.status_code == 200:
                        res_json = res_web.json()
                        if res_json.get("status") == "SUCESSO":
                            sucessos += 1
                except Exception:
                    pass
                
                barra.progress((i + 1) / total)
            st.success(f"Processamento concluído! {sucessos} de {total} salvos com sucesso.")

elif menu == "✍️ Formulário Manual":
    st.subheader(f"✍️ Manual - Sup: {supervisor} / Sub: {sub}")
    titulo = st.text_input("Título de Eleitor")
    nome = st.text_input("Nome Completo")
    cpf = st.text_input("CPF")
    
    if st.button("Salvar Cadastro Manual"):
        if titulo and nome:
            payload = {
                "titulo": titulo,
                "nome": nome,
                "cpf": cpf,
                "supervisor": supervisor,
                "subsupervisor": sub
            }
            try:
                res = requests.post(WEBHOOK_URL, json=payload)
                if res.status_code == 200:
                    resposta_servidor = res.json()
                    if resposta_servidor.get("status") == "DUPLICADO":
                        st.warning(resposta_servidor.get("mensagem"))
                    else:
                        st.success("Cadastro salvo com sucesso!")
                else:
                    st.error("Erro ao enviar.")
            except Exception as e:
                st.error(f"Erro: {e}")
        else:
            st.warning("Preencha ao menos o Título e o Nome.")
