import gc
import io
import pandas as pd
import streamlit as st
import sheets
import cruzamento
from streamlit_paste_button import paste_image_button

from leitor_documentos import preparar_documento
from extrator_documentos import analisar_documentos



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

    arquivos_upload = st.file_uploader(
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

    st.caption(
        "Ou copie uma foto/print e clique abaixo para colar."
    )

    imagem_colada = paste_image_button(
        "📋 Colar foto da área de transferência",
        key=f"colar_foto_{st.session_state['lote_upload_id']}",
        errors="raise"
    )

    if (
        imagem_colada is not None
        and imagem_colada.image_data is not None
    ):
        buffer_colado = io.BytesIO()
        imagem_colada.image_data.convert("RGB").save(
            buffer_colado,
            format="PNG"
        )
        st.session_state["_imagem_colada_bytes"] = (
            buffer_colado.getvalue()
        )

    arquivos = list(arquivos_upload or [])

    bytes_imagem_colada = st.session_state.get(
        "_imagem_colada_bytes"
    )

    if bytes_imagem_colada:
        arquivo_colado = io.BytesIO(
            bytes_imagem_colada
        )
        arquivo_colado.name = "imagem_colada.png"
        arquivos.append(arquivo_colado)

        st.success(
            "📋 Foto colada e pronta para processar."
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

            # Carrega as bases concorrentes uma única vez para todo o lote.
            consulta_bases_cruzamento = cruzamento.carregar_bases(
                webhook_url
            )

            bases_cruzamento = (
                consulta_bases_cruzamento.get("bases", {})
                if consulta_bases_cruzamento.get("sucesso")
                else {}
            )

            st.session_state["bases_cruzamento_lote"] = bases_cruzamento

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
                    arquivo_bytes = arquivo.getvalue()

                    # Mantém preparar_documento para não alterar a estrutura
                    # da tela, mas a EXTRAÇÃO CADASTRAL passa pelo motor OCR
                    # fornecido pelo processamento_documentos.
                    documento = preparar_documento(
                        arquivo.name,
                        arquivo_bytes
                    )

                    tipo = documento.get("tipo", "")

                    # IMPORTANTE:
                    # antes, PDFs que possuíam qualquer camada de texto
                    # desviavam do RapidOCR. Agora todos os documentos de
                    # cadastro passam pelo mesmo ler_documento/extrair_dados.
                    arquivo.seek(0)
                    texto, itens, tipo_ocr = ler_documento(
                        arquivo
                    )

                    if tipo_ocr:
                        tipo = tipo_ocr

                    dados = extrair_dados(
                        texto,
                        itens,
                        tipo,
                        nome_arquivo=arquivo.name
                    )

                    duplicado, existente = verificar_duplicidade(
                        dados,
                        base
                    )

                    resultado = classificar_resultado(
                        dados,
                        duplicado
                    )

                    # Cruzamento do título com as bases concorrentes.
                    bases_encontradas = ""
                    titulo_cruzado = str(dados.get("titulo", "") or "").strip()

                    if titulo_cruzado:
                        consulta_cruzamento = cruzamento.cruzar_titulo(
                            titulo_cruzado,
                            bases_cruzamento
                        )

                        bases_encontradas = str(
                            consulta_cruzamento.get("texto", "") or ""
                        ).strip()

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
                                existente_sup,

                            "Bases encontradas":
                                bases_encontradas,

                            "_titulo_cruzado":
                                titulo_cruzado,

                            "_dados":
                                dados
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
                "Confira e ajuste os dados abaixo quando necessário."
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

                # Conferência manual completa.
                # Todos os campos ficam editáveis após o OCR, inclusive os que
                # não foram identificados ou foram identificados incorretamente.
                col_nome, col_nasc = st.columns([2.2, 1])

                with col_nome:
                    nome_editado = st.text_input(
                        "Nome",
                        value=str(dados_item.get("nome", "") or ""),
                        key=f"nome_manual_{indice_item}_{arquivo_item}",
                        placeholder="Digite o nome"
                    ).strip().upper()

                with col_nasc:
                    nascimento_editado = st.text_input(
                        "Nascimento",
                        value=str(dados_item.get("data_nascimento", "") or ""),
                        key=f"nascimento_manual_{indice_item}_{arquivo_item}",
                        placeholder="DD/MM/AAAA"
                    ).strip()

                col_cpf, col_rg, col_titulo, col_zona, col_secao = st.columns(
                    [1.15, 1, 1.35, 0.7, 0.7]
                )

                with col_cpf:
                    cpf_editado = st.text_input(
                        "CPF",
                        value=str(dados_item.get("cpf", "") or ""),
                        key=f"cpf_manual_{indice_item}_{arquivo_item}",
                        placeholder="Somente números"
                    ).strip()

                with col_rg:
                    rg_editado = st.text_input(
                        "RG",
                        value=str(dados_item.get("rg", "") or ""),
                        key=f"rg_manual_{indice_item}_{arquivo_item}",
                        placeholder="RG"
                    ).strip()

                with col_titulo:
                    titulo_editado = st.text_input(
                        "Título",
                        value=str(dados_item.get("titulo", "") or ""),
                        key=f"titulo_manual_{indice_item}_{arquivo_item}",
                        placeholder="Título de eleitor"
                    ).strip()

                with col_zona:
                    zona_editada = st.text_input(
                        "Zona",
                        value=str(dados_item.get("zona", "") or ""),
                        key=f"zona_manual_{indice_item}_{arquivo_item}",
                        placeholder="Zona"
                    ).strip()

                with col_secao:
                    secao_editada = st.text_input(
                        "Seção",
                        value=str(dados_item.get("secao", "") or ""),
                        key=f"secao_manual_{indice_item}_{arquivo_item}",
                        placeholder="Seção"
                    ).strip()

                col_mae, col_tel = st.columns([2.2, 1])

                with col_mae:
                    mae_editada = st.text_input(
                        "Nome da mãe",
                        value=str(dados_item.get("nome_mae", "") or ""),
                        key=f"mae_manual_{indice_item}_{arquivo_item}",
                        placeholder="Digite o nome da mãe"
                    ).strip().upper()

                with col_tel:
                    telefone_editado = st.text_input(
                        "Telefone",
                        value=str(dados_item.get("telefone", "") or ""),
                        key=f"telefone_manual_{indice_item}_{arquivo_item}",
                        placeholder="82999999999"
                    ).strip()

                # Atualiza o dicionário usado pela validação e pelo salvamento.
                dados_item["nome"] = nome_editado
                dados_item["data_nascimento"] = nascimento_editado
                dados_item["cpf"] = cpf_editado
                dados_item["titulo"] = titulo_editado
                dados_item["rg"] = rg_editado
                dados_item["nome_mae"] = mae_editada
                dados_item["zona"] = zona_editada
                dados_item["secao"] = secao_editada

                # Se o título foi digitado/corrigido manualmente, refaz o cruzamento.
                titulo_atual_cruzamento = str(
                    dados_item.get("titulo", "") or ""
                ).strip()
                titulo_ja_cruzado = str(
                    item.get("_titulo_cruzado", "") or ""
                ).strip()

                if titulo_atual_cruzamento != titulo_ja_cruzado:
                    bases_atualizadas = ""

                    if titulo_atual_cruzamento:
                        bases_cruzamento_edicao = st.session_state.get(
                            "bases_cruzamento_lote",
                            {}
                        )

                        if not bases_cruzamento_edicao:
                            consulta_bases_edicao = cruzamento.carregar_bases(
                                webhook_url
                            )

                            if consulta_bases_edicao.get("sucesso"):
                                bases_cruzamento_edicao = consulta_bases_edicao.get(
                                    "bases",
                                    {}
                                )

                                st.session_state[
                                    "bases_cruzamento_lote"
                                ] = bases_cruzamento_edicao

                        consulta_cruzamento = cruzamento.cruzar_titulo(
                            titulo_atual_cruzamento,
                            bases_cruzamento_edicao
                        )

                        bases_atualizadas = str(
                            consulta_cruzamento.get("texto", "") or ""
                        ).strip()

                    item["Bases encontradas"] = bases_atualizadas
                    item["_titulo_cruzado"] = titulo_atual_cruzamento

                if telefone_editado:
                    dados_item["telefone"] = normalizar_telefone(
                        telefone_editado
                    )
                else:
                    dados_item["telefone"] = ""

                # Mantém também a linha-resumo sincronizada.
                item["Nome"] = dados_item["nome"]
                item["CPF"] = dados_item["cpf"]
                item["Título"] = dados_item["titulo"]
                item["Nascimento"] = dados_item["data_nascimento"]
                item["Nome da mãe"] = dados_item["nome_mae"]
                item["Zona"] = dados_item["zona"]
                item["Seção"] = dados_item["secao"]
                item["Telefone"] = dados_item["telefone"]

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

                bases_exibicao = str(
                    item.get("Bases encontradas", "") or ""
                ).strip()

                if bases_exibicao:
                    st.caption(
                        f"🎯 Cruzamento: {bases_exibicao}"
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
                st.session_state.pop("bases_cruzamento_lote", None)
                st.session_state.pop("_imagem_colada_bytes", None)

                # Remove apenas estados temporários dos campos do lote atual.
                for chave in list(st.session_state.keys()):
                    if (
                        str(chave).startswith("nome_manual_")
                        or str(chave).startswith("nascimento_manual_")
                        or str(chave).startswith("cpf_manual_")
                        or str(chave).startswith("titulo_manual_")
                        or str(chave).startswith("rg_manual_")
                        or str(chave).startswith("mae_manual_")
                        or str(chave).startswith("telefone_manual_")
                        or str(chave).startswith("zona_manual_")
                        or str(chave).startswith("secao_manual_")
                        or str(chave).startswith("mae_compacta_")
                        or str(chave).startswith("telefone_compacto_")
                    ):
                        del st.session_state[chave]

                # Trocar a chave do uploader faz o Streamlit limpar
                # todos os arquivos selecionados de uma vez.
                st.session_state["lote_upload_id"] += 1
                st.rerun()
