import streamlit as st
import requests
from google import genai
from google.genai import types
import json

# Configuração da página
st.set_page_config(page_title="Sistema de Cadastro CP", layout="centered", page_icon="🗳️")

# Lendo as chaves do cofre de segurança (Secrets) do Streamlit
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
            barra_progresso = st.progress(0)
            total = len(arquivos)
            
            sucessos = 0
            for i, arquivo in enumerate(arquivos):
                bytes_dados = arquivo.getvalue()
                
                # Definindo o tipo MIME correto
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
                    # Chamada oficial da SDK moderna do Gemini
                    resposta = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[
                            types.Part.from_bytes(data=bytes_dados, mime_type=mime_type),
                            prompt_extracao
                        ]
                    )
                    
                    # Limpando a resposta para garantir que seja um JSON puro
                    texto_resposta = resposta.text.replace("```json", "").replace("```", "").strip()
                    dados_extraidos = json.loads(texto_resposta)
                    
                    # Adicionando os metadados do operador
                    dados_extraidos["supervisor"] = supervisor
                    dados_extraidos["subsupervisor"] = sub
                    
                    # Enviando para o Webhook do Google Sheets
                    response_webhook = requests.post(WEBHOOK_URL, json=dados_extraidos)
                    
                    if response_webhook.status_code == 200:
                        sucessos += 1
                    else:
                        st.error(f"Erro ao salvar no Sheets o arquivo: {arquivo.name}")
                        
                except Exception as e:
                    st.error(f"Erro ao processar {arquivo.name}: {e}")
                
                # Atualiza a barra de progresso
                barra_progresso.progress((i + 1) / total)
            
            st.success(f"Processamento concluído! {sucessos} de {total} arquivo(s) salvos com sucesso.")

elif menu == "✍️ Formulário Manual":
    st.subheader("Cadastro Manual")
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
                    st.success("Cadastro manual salvo com sucesso no Google Sheets!")
                else:
                    st.error("Erro ao enviar para o Google Sheets.")
            except Exception as e:
                st.error(f"Erro de conexão: {e}")
        else:
            st.warning("Preencha ao menos o Título de Eleitor e o Nome.")
