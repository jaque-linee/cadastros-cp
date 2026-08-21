import streamlit as st
import requests
import re

import sheets


def somente_numeros(valor):
    return re.sub(r"\D", "", str(valor or ""))


def exibir_tela_formulario_manual(base, webhook_url, supervisor, sub):
    """Exibe a consulta e o cadastro manual."""

    st.subheader(
        "✍️ Consulta & Cadastro Manual"
    )

    if (
        "busca_realizada"
        not in st.session_state
    ):
        st.session_state.update(
            {
                "busca_realizada":
                    False,

                "titulo":
                    "",

                "encontrado":
                    None,

                "bases_encontradas_manual":
                    []
            }
        )

    # Garante a chave mesmo em sessão antiga já aberta.
    if "bases_encontradas_manual" not in st.session_state:
        st.session_state["bases_encontradas_manual"] = []

    titulo_input = st.text_input(
        "Título de Eleitor:",
        value=st.session_state.titulo
    )

    if st.button(
        "🔍 Pesquisar"
    ):
        st.session_state.titulo = (
            titulo_input
        )

        titulo_pesquisado = somente_numeros(
            titulo_input
        ).lstrip(
            "0"
        )

        encontrado = None

        for pessoa in base:
            titulo_base = somente_numeros(
                pessoa.get(
                    "titulo",
                    ""
                )
            ).lstrip(
                "0"
            )

            if (
                titulo_pesquisado
                and titulo_base
                == titulo_pesquisado
            ):
                encontrado = pessoa
                break

        st.session_state.encontrado = (
            encontrado
        )

        # ========================================================
        # CRUZAMENTO — MESMA FONTE USADA PELO RELATÓRIO
        # ========================================================

        bases_encontradas = []

        consulta_concorrentes = sheets.carregar_concorrentes(
            webhook_url
        )

        if consulta_concorrentes.get("sucesso"):
            # Mesma normalização usada pelo relatório de cruzamentos:
            # somente números + remoção dos zeros à esquerda.
            titulo_normalizado = (
                somente_numeros(
                    titulo_input
                ).lstrip("0")
            )

            for nome_base, titulos in consulta_concorrentes.get(
                "dados",
                {}
            ).items():

                titulos_normalizados = {
                    somente_numeros(
                        titulo_base
                    ).lstrip("0")
                    for titulo_base in (titulos or [])
                    if somente_numeros(
                        titulo_base
                    )
                }

                if (
                    titulo_normalizado
                    and titulo_normalizado
                    in titulos_normalizados
                ):
                    bases_encontradas.append(
                        str(nome_base)
                    )

        st.session_state[
            "bases_encontradas_manual"
        ] = bases_encontradas

        st.session_state.busca_realizada = (
            True
        )

    if st.session_state.busca_realizada:

        # Mostra o cruzamento independentemente de já estar
        # cadastrado ou não na base principal.
        bases_manual = st.session_state.get(
            "bases_encontradas_manual",
            []
        )

        if bases_manual:
            st.warning(
                "🎯 Cruzamento encontrado: "
                + " | ".join(bases_manual)
            )

        if st.session_state.encontrado:
            e = st.session_state.encontrado

            st.error(
                f"⚠️ Já cadastrado: "
                f"{e.get('nome')} | "
                f"Supervisor: "
                f"{e.get('supervisor')}"
            )

            if st.button(
                "Limpar"
            ):
                st.session_state.busca_realizada = (
                    False
                )

                st.session_state.encontrado = (
                    None
                )

                st.session_state.titulo = ""

                st.session_state[
                    "bases_encontradas_manual"
                ] = []

                st.rerun()

        else:
            st.success(
                "Título não localizado na base. "
                "O cadastro pode ser realizado."
            )

            with st.form(
                "cadastro_manual"
            ):
                nome = st.text_input(
                    "Nome *"
                )

                cpf = st.text_input(
                    "CPF"
                )

                data_nasc = st.text_input(
                    "Data de Nascimento "
                    "(DD/MM/AAAA)"
                )

                nome_mae = st.text_input(
                    "Nome da mãe"
                )

                salvar = st.form_submit_button(
                    "💾 Salvar"
                )

                if salvar:
                    if not nome:
                        st.error(
                            "Informe o nome."
                        )

                    else:
                        payload = {
                            "titulo":
                                st.session_state.titulo,

                            "nome":
                                nome,

                            "cpf":
                                cpf,

                            "data_nascimento":
                                data_nasc,

                            "nome_mae":
                                nome_mae,

                            "supervisor":
                                supervisor,

                            "subsupervisor":
                                sub
                        }

                        try:
                            resposta = requests.post(
                                webhook_url,
                                json=payload,
                                timeout=30
                            )

                            resultado = resposta.json()

                            if (
                                resultado.get(
                                    "status"
                                )
                                == "SUCESSO"
                            ):
                                st.success(
                                    "Salvo com sucesso!"
                                )

                                st.cache_data.clear()

                                st.session_state.busca_realizada = (
                                    False
                                )

                                st.session_state.encontrado = (
                                    None
                                )

                                st.session_state.titulo = ""

                                st.session_state[
                                    "bases_encontradas_manual"
                                ] = []

                                st.rerun()

                            else:
                                st.error(
                                    resultado.get(
                                        "mensagem",
                                        "Erro ao salvar."
                                    )
                                )

                        except Exception as erro:
                            st.error(
                                f"Erro ao salvar: {erro}"
                            )


    # ============================================================
    # 28. RELATÓRIOS
    # ============================================================
