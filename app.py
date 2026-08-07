import streamlit as st

# Configuração da página para ficar moderna e responsiva
st.set_page_config(page_title="Sistema de Cadastro CP", layout="centered", page_icon="🗳️")

st.title("🗳️ Sistema de Cadastro CP")
st.markdown("---")

# Menu Lateral (Sidebar)
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
            st.info("Processando arquivos... aguarde a barra de progresso.")

elif menu == "✍️ Formulário Manual":
    st.subheader("Cadastro Manual")
    titulo = st.text_input("Título de Eleitor")
    if st.button("Buscar Título"):
        st.warning("Verificando duplicidade...")
