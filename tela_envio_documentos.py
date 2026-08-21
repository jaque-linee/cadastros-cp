import gc
import pandas as pd
import streamlit as st
import sheets



def normalizar_telefone(valor):
    numeros = "".join(ch for ch in str(valor or "") if ch.isdigit())
    if len(numeros) == 11:
        return f"({numeros[:2]}) {numeros[2:7]}-{numeros[7:]}"
    if len(numeros) == 10:
        return f"({numeros[:2]}) {numeros[2:6]}-{numeros[6:]}"
    return numeros


def exibir_tela_envio_documentos(
    base,
    supervisor,
    sub,
    ler_documento,
    extrair_dados,
    verificar_duplicidade,
    classificar_resultado,
    webhook_url,
    comunidade,
):
    """Exibe upload, processamento e resultado do lote de documentos."""

    st.subheader(
        "📁 Processamento de Documentos"
    )

    if "lote_upload_id" not in st.session_state:
        st.session_state["lote_upload_id"] = 0


    st.caption(
        f"Supervisor: {supervisor} | "
        f"Subsupervisor: {sub}"
    )

    arquivos = st.file_uploader(
        "Selecione fotos ou PDFs",
        accept_multiple_files=True,
        type=[
            "pdf",
            "jpg",
            "jpeg",
            "png"
        ],
        key=f"uploader_lote_{st.session_state['lote_upload_id']}"
    )

    if arquivos:
        st.info(
            f"{len(arquivos)} arquivo(s) selecionado(s). "
            "Cada documento será processado individualmente."
        )

        if st.button(
            "🔎 Processar Lote"
        ):
            resultados = []

            total = len(
                arquivos
            )

            barra = st.progress(
                0
            )

            status_area = st.empty()

            for indice, arquivo in enumerate(
                arquivos
            ):
                status_area.info(
                    f"Processando "
                    f"{indice + 1} de {total}: "
                    f"{arquivo.name}"
                )

                try:
                    texto, itens, tipo = ler_documento(
                        arquivo
                    )

                    dados = extrair_dados(
                        texto,
                        itens,
                        tipo
                    )

                    duplicado, existente = verificar_duplicidade(
                        dados,
                        base
                    )

                    resultado = classificar_resultado(
                        dados,
                        duplicado
                    )

                    existente_nome = ""
                    existente_sup = ""

                    if duplicado and existente:
                        existente_nome = str(
                            existente.get(
                                "nome",
                                ""
                            )
                        )

                        existente_sup = str(
                            existente.get(
                                "supervisor",
                                ""
                            )
                        )

                    resultados.append(
                        {
                            "Arquivo":
                                arquivo.name,

                            "Nome":
                                dados["nome"],

                            "CPF":
                                dados["cpf"],

                            "Título":
                                dados["titulo"],

                            "Nascimento":
                                dados[
                                    "data_nascimento"
                                ],

                            "Nome da mãe":
                                dados[
                                    "nome_mae"
                                ],

                            "Zona":
                                dados["zona"],

                            "Seção":
                                dados["secao"],

                            "Leitura":
                                tipo,

                            "Resultado":
                                resultado,

                            "Já cadastrado como":
                                existente_nome,

                            "Supervisor atual":
                                existente_sup
                        }
                    )

                    del texto
                    del itens

                    gc.collect()

                except Exception as erro:
                    resultados.append(
                        {
                            "Arquivo":
                                arquivo.name,

                            "Nome":
                                "",

                            "CPF":
                                "",

                            "Título":
                                "",

                            "Nascimento":
                                "",

                            "Nome da mãe":
                                "",

                            "Zona":
                                "",

                            "Seção":
                                "",

                            "Leitura":
                                "",

                            "Resultado":
                                "❌ ERRO",

                            "Já cadastrado como":
                                "",

                            "Supervisor atual":
                                ""
                        }
                    )

                    st.error(
                        f"Erro em "
                        f"{arquivo.name}: "
                        f"{erro}"
                    )

                barra.progress(
                    (
                        indice + 1
                    )
                    / total
                )

                gc.collect()

            status_area.success(
                "Processamento concluído."
            )

            st.session_state[
                "resultado_lote"
            ] = resultados


    # ========================================================
    # RESULTADOS
    # ========================================================

    if (
        "resultado_lote"
        in st.session_state
    ):
        resultados = st.session_state[
            "resultado_lote"
        ]

        if resultados:
            completos = sum(
                1
                for r in resultados
                if r["Resultado"]
                == "✅ COMPLETO"
            )

            duplicados = sum(
                1
                for r in resultados
                if r["Resultado"]
                == "⚠️ JÁ CADASTRADO"
            )

            conferir = (
                len(resultados)
                - completos
                - duplicados
            )

            # ====================================================
            # RESULTADO COMPACTO / CONFERÊNCIA NA PRÓPRIA LINHA
            # ====================================================

            st.markdown(
                f"""
                <div style="
                    background:#ffffff;
                    border:1px solid #d9e1e8;
                    border-radius:10px;
                    padding:10px 14px;
                    margin:4px 0 12px 0;
                    font-size:0.95rem;
                ">
                    <b>📊 Resultado do lote</b>
                    &nbsp;&nbsp; ✅ {completos} completos
                    &nbsp;&nbsp; 🔁 {duplicados} já cadastrados
                    &nbsp;&nbsp; ⚠️ {conferir} conferir
                </div>
                """,
                unsafe_allow_html=True
            )

            st.caption(
                "Confira os dados abaixo. Telefone e nome da mãe podem ser "
                "ajustados na própria linha quando necessário."
            )

            for indice_item, item in enumerate(resultados):
                dados_item = item.get("_dados")

                if not dados_item:
                    st.error(
                        f"{item.get('Arquivo', 'Documento')} — "
                        f"{item.get('Resultado', '❌ ERRO')}"
                    )
                    continue

                nome_item = str(
                    dados_item.get("nome", "") or "NOME NÃO IDENTIFICADO"
                ).strip()

                resultado_item = str(
                    item.get("Resultado", "") or "⚠️ CONFERIR"
                ).strip()

                bases_item = str(
                    item.get("Bases encontradas", "") or ""
                ).strip()

                arquivo_item = str(
                    item.get("Arquivo", "Documento") or "Documento"
                ).strip()

                # Cabeçalho compacto de cada pessoa.
                cabecalho = (
                    f"**{nome_item}**  ·  {resultado_item}  ·  "
                    f"📄 {arquivo_item}"
                )

                if bases_item:
                    cabecalho += f"  ·  🎯 Base: **{bases_item}**"

                st.markdown(cabecalho)

                # Linha principal: documentos e localização.
                cpf_item = str(dados_item.get("cpf", "") or "—")
                titulo_item = str(dados_item.get("titulo", "") or "—")
                nasc_item = str(
                    dados_item.get("data_nascimento", "") or "—"
                )
                zona_item = str(dados_item.get("zona", "") or "—")
                secao_item = str(dados_item.get("secao", "") or "—")

                st.caption(
                    f"CPF: {cpf_item}   •   Título: {titulo_item}   •   "
                    f"Nascimento: {nasc_item}   •   "
                    f"Zona/Seção: {zona_item}/{secao_item}"
                )

                # Mãe e telefone ficam juntos, sem criar seções separadas.
                col_mae, col_tel = st.columns([2.2, 1])

                with col_mae:
                    mae_atual = str(
                        dados_item.get("nome_mae", "") or ""
                    ).strip().upper()

                    candidatos = []

                    for candidato in dados_item.get(
                        "_candidatos_mae",
                        []
                    ):
                        candidato = str(
                            candidato or ""
                        ).strip().upper()

                        if (
                            candidato
                            and candidato != nome_item.upper()
                            and candidato not in candidatos
                        ):
                            candidatos.append(candidato)

                    chave_mae = (
                        f"mae_compacta_{indice_item}_"
                        f"{arquivo_item}"
                    )

                    if not mae_atual and candidatos:
                        escolha_mae = st.selectbox(
                            "Nome da mãe",
                            options=["— SELECIONE —"] + candidatos,
                            key=chave_mae
                        )

                        if escolha_mae != "— SELECIONE —":
                            dados_item["nome_mae"] = escolha_mae
                            item["Nome da mãe"] = escolha_mae

                    elif mae_atual:
                        st.text_input(
                            "Nome da mãe",
                            value=mae_atual,
                            key=chave_mae,
                            disabled=True
                        )

                    else:
                        mae_digitada = st.text_input(
                            "Nome da mãe",
                            value="",
                            key=chave_mae,
                            placeholder="Digite se não foi identificada"
                        )

                        if str(mae_digitada).strip():
                            dados_item["nome_mae"] = (
                                str(mae_digitada).strip().upper()
                            )
                            item["Nome da mãe"] = dados_item["nome_mae"]

                with col_tel:
                    chave_tel = (
                        f"telefone_compacto_{indice_item}_"
                        f"{arquivo_item}"
                    )

                    telefone_atual = str(
                        dados_item.get("telefone", "") or ""
                    )

                    telefone_editado = st.text_input(
                        "Telefone",
                        value=telefone_atual,
                        key=chave_tel,
                        placeholder="82999999999"
                    )

                    if str(telefone_editado).strip():
                        telefone_limpo = normalizar_telefone(
                            telefone_editado
                        )
                    else:
                        telefone_limpo = ""

                    dados_item["telefone"] = telefone_limpo
                    item["Telefone"] = telefone_limpo

                # Reclassifica após eventual escolha/digitação do nome da mãe.
                if resultado_item != "⚠️ JÁ CADASTRADO":
                    duplicado_atual, _ = verificar_duplicidade(
                        dados_item,
                        base
                    )

                    item["Resultado"] = classificar_resultado(
                        dados_item,
                        duplicado_atual
                    )

                # Se já existe, mostra a referência de forma curta.
                if item.get("Resultado") == "⚠️ JÁ CADASTRADO":
                    cadastrado_como = str(
                        item.get("Já cadastrado como", "") or ""
                    ).strip()
                    supervisor_atual = str(
                        item.get("Supervisor atual", "") or ""
                    ).strip()

                    detalhes_duplicado = []

                    if cadastrado_como:
                        detalhes_duplicado.append(
                            f"já cadastrado como {cadastrado_como}"
                        )

                    if supervisor_atual:
                        detalhes_duplicado.append(
                            f"supervisor atual: {supervisor_atual}"
                        )

                    if detalhes_duplicado:
                        st.caption(
                            "↳ " + " • ".join(detalhes_duplicado)
                        )

                st.markdown(
                    "<div style='border-bottom:1px solid #d9e1e8; "
                    "margin:4px 0 10px 0;'></div>",
                    unsafe_allow_html=True
                )

            st.session_state[
                "resultado_lote"
            ] = resultados

            # ====================================================
            # SALVAR CADASTROS COMPLETOS NA TABELA
            # ====================================================

            aptos_para_salvar = [
                item
                for item in resultados
                if (
                    item.get("Resultado") == "✅ COMPLETO"
                    and item.get("_dados")
                )
            ]

            if aptos_para_salvar:

                st.info(
                    f"📥 {len(aptos_para_salvar)} cadastro(s) "
                    f"completo(s) pronto(s) para salvar."
                )

                if st.button(
                    "💾 Salvar completos na TABELA",
                    type="primary"
                ):
                    salvos = 0
                    duplicados_salvar = 0
                    erros_salvar = 0

                    progresso_salvar = st.progress(0)

                    for indice_salvar, item in enumerate(
                        aptos_para_salvar
                    ):
                        dados_salvar = dict(
                            item["_dados"]
                        )

                        dados_salvar.pop(
                            "_candidatos_mae",
                            None
                        )

                        dados_salvar[
                            "comunidade"
                        ] = comunidade

                        retorno = sheets.salvar_cadastro(
                            webhook_url,
                            dados_salvar,
                            supervisor,
                            sub,
                            dados_base=base
                        )

                        status_salvar = retorno.get(
                            "status",
                            "ERRO"
                        )

                        if status_salvar == "SUCESSO":
                            salvos += 1

                        elif status_salvar == "DUPLICADO":
                            duplicados_salvar += 1

                        else:
                            erros_salvar += 1

                            st.error(
                                f"{item['Arquivo']}: "
                                f"{retorno.get('mensagem', 'Erro ao salvar.')}"
                            )

                        progresso_salvar.progress(
                            (indice_salvar + 1)
                            / len(aptos_para_salvar)
                        )

                    st.success(
                        f"Salvamento concluído: "
                        f"{salvos} salvo(s), "
                        f"{duplicados_salvar} duplicado(s) "
                        f"e {erros_salvar} erro(s)."
                    )

                    st.cache_data.clear()

            st.caption(
                "ℹ️ Completo = Nome + Nascimento + Nome da mãe + "
                "CPF ou Título. Nenhum cadastro é gravado automaticamente."
            )

            if st.button(
                "🧹 Finalizar lote / Novo lote",
                use_container_width=True
            ):
                st.session_state.pop("resultado_lote", None)

                # Remove apenas estados temporários dos campos do lote atual.
                for chave in list(st.session_state.keys()):
                    if (
                        str(chave).startswith("mae_compacta_")
                        or str(chave).startswith("telefone_compacto_")
                    ):
                        del st.session_state[chave]

                # Trocar a chave do uploader faz o Streamlit limpar
                # todos os arquivos selecionados de uma vez.
                st.session_state["lote_upload_id"] += 1
                st.rerun()
