import streamlit as st
import tempfile
import os
import gc

from paddleocr import PaddleOCR


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Teste PaddleOCR",
    page_icon="🔎",
    layout="wide"
)

st.title("🔎 Teste de leitura — PaddleOCR")

st.caption(
    "Este teste mostra somente o que o PaddleOCR consegue ler. "
    "Nenhum dado será enviado para a planilha."
)


# ============================================================
# CARREGAR OCR
# ============================================================

@st.cache_resource
def carregar_ocr():

    return PaddleOCR(
        lang="pt",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False
    )


try:
    with st.spinner("Carregando PaddleOCR..."):
        ocr = carregar_ocr()

    st.success("PaddleOCR carregado.")

except Exception as erro:

    st.error("Não foi possível carregar o PaddleOCR.")

    st.exception(erro)

    st.stop()


# ============================================================
# UPLOAD
# ============================================================

arquivos = st.file_uploader(
    "Selecione os PDFs para testar",
    type=["pdf"],
    accept_multiple_files=True
)


# ============================================================
# PROCESSAR
# ============================================================

if arquivos:

    st.info(
        f"{len(arquivos)} arquivo(s) selecionado(s)."
    )

    if st.button(
        "🔎 TESTAR LEITURA",
        type="primary",
        use_container_width=True
    ):

        for indice, arquivo in enumerate(
            arquivos,
            start=1
        ):

            st.divider()

            st.subheader(
                f"{indice}. {arquivo.name}"
            )

            caminho_temporario = None

            try:

                # --------------------------------------------
                # SALVAR PDF TEMPORARIAMENTE
                # --------------------------------------------

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".pdf"
                ) as temp:

                    temp.write(
                        arquivo.getvalue()
                    )

                    caminho_temporario = (
                        temp.name
                    )


                # --------------------------------------------
                # EXECUTAR PADDLEOCR
                # --------------------------------------------

                with st.spinner(
                    f"Lendo {arquivo.name}..."
                ):

                    resultados = ocr.predict(
                        caminho_temporario
                    )


                # --------------------------------------------
                # MOSTRAR RESULTADO BRUTO
                # --------------------------------------------

                textos_encontrados = []

                for numero_pagina, resultado in enumerate(
                    resultados,
                    start=1
                ):

                    st.markdown(
                        f"### Página {numero_pagina}"
                    )

                    try:

                        dados = resultado.json

                        if callable(dados):
                            dados = dados()

                    except Exception:

                        dados = {}


                    # ----------------------------------------
                    # EXTRAIR SOMENTE TEXTOS RECONHECIDOS
                    # ----------------------------------------

                    textos_pagina = []

                    if isinstance(
                        dados,
                        dict
                    ):

                        res = dados.get(
                            "res",
                            dados
                        )

                        if isinstance(
                            res,
                            dict
                        ):

                            textos = res.get(
                                "rec_texts",
                                []
                            )

                            scores = res.get(
                                "rec_scores",
                                []
                            )

                            for posicao, texto in enumerate(
                                textos
                            ):

                                texto = str(
                                    texto or ""
                                ).strip()

                                if not texto:
                                    continue

                                confianca = ""

                                if (
                                    isinstance(
                                        scores,
                                        list
                                    )
                                    and posicao
                                    < len(scores)
                                ):

                                    try:

                                        confianca = (
                                            f" "
                                            f"[{float(scores[posicao]):.2f}]"
                                        )

                                    except Exception:
                                        pass


                                textos_pagina.append(
                                    texto
                                )

                                st.write(
                                    f"{texto}"
                                    f"{confianca}"
                                )


                    if not textos_pagina:

                        st.warning(
                            "Nenhum texto foi recuperado "
                            "desta página."
                        )

                        with st.expander(
                            "Ver resultado bruto"
                        ):

                            st.write(
                                resultado
                            )


                    textos_encontrados.extend(
                        textos_pagina
                    )


                # --------------------------------------------
                # TEXTO COMPLETO
                # --------------------------------------------

                st.markdown(
                    "### 📄 Texto completo encontrado"
                )

                if textos_encontrados:

                    st.text_area(
                        "Resultado",
                        value="\n".join(
                            textos_encontrados
                        ),
                        height=400,
                        key=f"resultado_{indice}"
                    )

                else:

                    st.warning(
                        "O PaddleOCR não retornou "
                        "texto aproveitável."
                    )


            except Exception as erro:

                st.error(
                    f"Erro ao processar "
                    f"{arquivo.name}"
                )

                st.exception(
                    erro
                )


            finally:

                # --------------------------------------------
                # LIMPEZA
                # --------------------------------------------

                if (
                    caminho_temporario
                    and os.path.exists(
                        caminho_temporario
                    )
                ):

                    try:

                        os.remove(
                            caminho_temporario
                        )

                    except Exception:
                        pass


                gc.collect()
