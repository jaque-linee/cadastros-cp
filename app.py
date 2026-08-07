import streamlit as st
import requests
from google import genai
from google.genai import types
import json
import pandas as pd

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

# 1. Menu Principal focado primeiro em consultar/puxar os cadastrados
menu_principal = st.selectbox("Selecione a Ação:", [
    "📋 Consultar Cadastrados", 
    "📸 Envio de Documentos (Lote)", 
    "✍️ Formulário Manual"
])

# Seletor de Supervisor/Sub comum para as operações
col1, col2 = st.columns(2)
with col1:
    supervisor = st.selectbox("Supervisor", ["ADEILTON", "ADRIANO BATISTA", "TESTE"])
with col2:
    sub = st.text_input("Subsupervisor", "SEM SUBSUPERVISOR")

st.markdown("---")

if menu_principal == "📋 Consultar Cadastrados":
    st.subheader("Cadastrados na Base")
    st.info("Aqui você poderá puxar e visualizar a listagem de todos os registros salvos.")
    
    if st.button("🔄 Puxar / Atualizar Lista"):
        try:
            # Enviando um pedido GET ou POST de listagem para o Webhook (dependendo de como configurou o Apps Script)
            response = requests.get(WEBHOOK_URL)
            if response.status_code == 200:
                dados = response.json()
                if dados:
                    df = pd.DataFrame(dados)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.warning("Nenhum cadastro encontrado na planilha.")
            else:
                st.error("Erro ao conectar com a planilha para puxar os dados.")
        except Exception as e:
            st.warning("Ainda ajustando a rota de leitura do Sheets. O botão está pronto para quando a rota GET estiver ativa.")

elif menu_principal == "📸 Envio de Documentos (Lote)":
    st.subheader("Upload de Documentos em Lote")
    arquivos = st.file_uploader("Arraste ou escolha as fotos/PDFs", accept_multiple_files=True, type=['pdf', 'jpg', 'png'])
    
    if arquivos:
        if st.button("Processar e Enviar Lote"):
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

elif menu_principal == "✍️ Formulário Manual":
    st.subheader("Cadastro Manual Individual")
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
