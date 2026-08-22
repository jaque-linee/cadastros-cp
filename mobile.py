import streamlit as st


# ============================================================
# BASE MOBILE - TESTE DE COMPATIBILIDADE
# ============================================================

st.set_page_config(
    page_title="BASE Mobile",
    page_icon="📱",
    layout="centered"
)


# ============================================================
# VISUAL
# ============================================================

st.markdown(
    """
    <style>
        .stApp {
            background-color: #eef2f5;
        }

        .block-container {
            max-width: 600px;
            padding-top: 1.5rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }

        div.stButton > button {
            width: 100%;
            background-color: #0056b3;
            color: white;
            border-radius: 10px;
            font-weight: bold;
        }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# CABEÇALHO
# ============================================================

st.title("📱 BASE Mobile")

st.caption(
    "Consulta rápida por documento"
)

st.markdown("---")


# ============================================================
# FOTO
# ============================================================

st.subheader("📷 Consultar documento")

foto = st.file_uploader(
    "Selecione uma foto",
    type=["jpg", "jpeg", "png"]
)


if foto is not None:

    st.image(
        foto,
        caption="Documento selecionado",
        use_container_width=True
    )

    if st.button(
        "🔎 Consultar"
    ):
        st.success(
            "Foto recebida com sucesso!"
        )

        st.info(
            "Próximo passo: conectar esta foto "
            "ao leitor de títulos do BASE."
        )
