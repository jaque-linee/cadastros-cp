import gc
import uuid
import io
import re
import pandas as pd
import streamlit as st
import sheets
import cruzamento
from streamlit_paste_button import paste_image_button

from leitor_documentos import preparar_documento
from extrator_documentos import analisar_documentos
from gemini_documentos import (
    ler_documento_gemini,
    pode_chamar_gemini,
    LIMITE_DOCUMENTOS_SESSAO,
    LIMITE_ESTIMADO_BRL_SESSAO,
    MODELO_GEMINI,
)



def normalizar_telefone(valor):
    numeros = "".join(ch for ch in str(valor or "") if ch.isdigit())
    if len(numeros) == 11:
        return f"({numeros[:2]}) {numeros[2:7]}-{numeros[7:]}"
    if len(numeros) == 10:
        return f"({numeros[:2]}) {numeros[2:6]}-{numeros[6:]}"
    return numeros



def _obter_gemini_api_key():
    try:
        return str(st.secrets.get("GEMINI_API_KEY", "") or "").strip()
    except Exception:
        return ""


def _consumo_gemini():
    padrao = {
        "documentos": 0, "prompt_tokens": 0, "output_tokens": 0,
        "total_tokens": 0, "custo_brl": 0.0, "custo_usd": 0.0
    }
    if "gemini_consumo_sessao" not in st.session_state:
        st.session_state["gemini_consumo_sessao"] = padrao.copy()
    return st.session_state["gemini_consumo_sessao"]


def _registrar_gemini(uso):
    c = _consumo_gemini()
    c["documentos"] += 1
    c["prompt_tokens"] += int(uso.get("prompt_tokens", 0) or 0)
    c["output_tokens"] += int(uso.get("output_tokens", 0) or 0)
    c["total_tokens"] += int(uso.get("total_tokens", 0) or 0)
    c["custo_brl"] += float(uso.get("custo_brl_estimado", 0) or 0)
    c["custo_usd"] += float(uso.get("custo_usd_estimado", 0) or 0)
    return c


def _monitor_gemini(local=None):
    c = _consumo_gemini()
    msg = (
        f"🤖 Gemini híbrido ({MODELO_GEMINI}) — "
        f"{c['documentos']}/{LIMITE_DOCUMENTOS_SESSAO} chamadas úteis · "
        f"{c['prompt_tokens']} tokens entrada · {c['output_tokens']} saída · "
        f"**R$ {c['custo_brl']:.4f} estimados** · trava R$ {LIMITE_ESTIMADO_BRL_SESSAO:.2f}"
    )
    (local.info if local is not None else st.info)(msg)


def _nome_suspeito_para_gemini(valor):
    """Detecta quando o OCR colocou outro campo no lugar do NOME."""
    nome = str(valor or "").strip().upper()

    if not nome:
        return True

    termos_invalidos = (
        "ENDEREÇO", "ENDERECO", "CIDADE", "BAIRRO", "COMUNIDADE",
        "Nº TÍTULO", "N° TÍTULO", "N TITULO", "TÍTULO", "TITULO",
        "ZONA", "SEÇÃO", "SECAO", "DATA DE NASCIMENTO", "NASCIMENTO",
        "TELEFONE", "NOME DA MÃE", "NOME DA MAE",
        "SUPERVISOR", "SUBSUPERVISOR",
    )

    if any(termo in nome for termo in termos_invalidos):
        return True

    if any(ch.isdigit() for ch in nome):
        return True

    palavras = re.findall(r"[A-ZÀ-Ü]+", nome)
    if len(palavras) < 2:
        return True

    return False


def _campos_para_gemini(dados):
    """
    Gemini complementa lacunas e confere filiação.
    Título, zona e seção formam um conjunto: se QUALQUER um faltar,
    os três são enviados juntos para leitura no documento inteiro.
    """
    alvos = []

    for campo in (
        "nome",
        "cpf",
        "rg",
        "data_nascimento",
        "telefone",
    ):
        valor = str(dados.get(campo, "") or "").strip()

        if not valor:
            alvos.append(campo)
            continue

        if campo == "nome" and _nome_suspeito_para_gemini(valor):
            alvos.append("nome")

    eleitorais = ("titulo", "zona", "secao")
    if any(
        not str(dados.get(campo, "") or "").strip()
        for campo in eleitorais
    ):
        for campo in eleitorais:
            if campo not in alvos:
                alvos.append(campo)

    # Filiação precisa ser conferida mesmo quando o OCR trouxe um nome:
    # o primeiro nome do bloco pode ser o pai.
    alvos.append("nome_mae")

    return alvos


def _mesclar_gemini(dados, dados_gemini, campos_alvo):
    """
    Gemini preenche lacunas.
    Para nome_mae, a conferência visual do Gemini pode corrigir o RapidOCR,
    inclusive quando o OCR capturou o pai por engano.
    """
    for campo in campos_alvo:
        atual = str(dados.get(campo, "") or "").strip()
        novo = str(dados_gemini.get(campo, "") or "").strip()

        if campo == "nome_mae":
            if novo:
                dados[campo] = novo
            continue

        if campo == "nome":
            if novo and (not atual or _nome_suspeito_para_gemini(atual)):
                dados[campo] = novo
            continue

        # Quando o conjunto eleitoral foi acionado, a leitura direcionada
        # do Gemini pode corrigir título/zona/seção já preenchidos pelo OCR.
        if campo in ("titulo", "zona", "secao"):
            if novo:
                dados[campo] = novo
            continue

        if not atual and novo:
            dados[campo] = novo

    return dados


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

    _monitor_gemini()

    if "lote_upload_id" not in st.session_state:
        st.session_state["lote_upload_id"] = 0

    # ID persistente do lote atual. O rascunho fica no Google Sheets,
    # portanto sobrevive a queda/reinício do Streamlit.
    if "lote_persistente_id" not in st.session_state:
        st.session_state["lote_persistente_id"] = ""

    if "resultado_lote" not in st.session_state:
        if st.button("♻️ Recuperar último lote não finalizado", use_container_width=True):
            recuperado = sheets.carregar_ultimo_rascunho(
                webhook_url,
                supervisor,
                sub
            )
            if recuperado.get("sucesso") and recuperado.get("resultados"):
                st.session_state["resultado_lote"] = recuperado["resultados"]
                st.session_state["lote_persistente_id"] = recuperado["lote_id"]
                st.success(
                    f"Rascunho recuperado: {len(recuperado['resultados'])} documento(s)."
                )
                st.rerun()
            else:
                st.info("Nenhum lote pendente encontrado para recuperar.")


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
            st.session_state["lote_persistente_id"] = (
                "LOTE-" + uuid.uuid4().hex[:12].upper()
            )

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
            gemini_area = st.empty()
            _monitor_gemini(gemini_area)

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
                        arquivo.name
                    )

                    # HÍBRIDO: RapidOCR primeiro.
                    # Se o NOME veio suspeito, faz uma chamada EXCLUSIVA ao Gemini
                    # para o nome antes de qualquer outra conferência.
                    campos_alvo = _campos_para_gemini(dados)
                    api_key_gemini = _obter_gemini_api_key()

                    nome_precisa_gemini = _nome_suspeito_para_gemini(
                        dados.get("nome", "")
                    )

                    if nome_precisa_gemini and api_key_gemini:
                        consumo = _consumo_gemini()
                        permitido_nome, motivo_nome = pode_chamar_gemini(
                            consumo["documentos"],
                            consumo["custo_brl"]
                        )

                        if permitido_nome:
                            try:
                                retorno_nome = ler_documento_gemini(
                                    arquivo_bytes,
                                    arquivo.name,
                                    api_key_gemini,
                                    timeout=12,
                                    campos_alvo=["nome"]
                                )

                                dados = _mesclar_gemini(
                                    dados,
                                    retorno_nome["dados"],
                                    ["nome"]
                                )

                                _registrar_gemini(retorno_nome["uso"])
                                _monitor_gemini(gemini_area)

                            except Exception as erro_nome:
                                st.caption(
                                    f"⚠️ Gemini não conseguiu conferir o NOME "
                                    f"de {arquivo.name}: {erro_nome}"
                                )
                        else:
                            st.caption(
                                f"🔒 Gemini pausado para NOME: {motivo_nome}"
                            )

                    # Recalcula os alvos após a tentativa exclusiva do NOME.
                    # Remove nome da chamada geral para não pagar/processar duas vezes.
                    campos_alvo = [
                        campo
                        for campo in _campos_para_gemini(dados)
                        if campo != "nome"
                    ]

                    if campos_alvo and api_key_gemini:
                        consumo = _consumo_gemini()
                        permitido, motivo = pode_chamar_gemini(
                            consumo["documentos"],
                            consumo["custo_brl"]
                        )

                        if permitido:
                            criticos = [
                                campo for campo in (
                                    "cpf",
                                    "titulo",
                                    "zona",
                                    "secao",
                                    "data_nascimento"
                                )
                                if campo in campos_alvo
                            ]

                            if criticos:
                                alvos_chamada = criticos
                                timeout_gemini = 18
                            else:
                                alvos_chamada = campos_alvo
                                timeout_gemini = 10

                            try:
                                retorno_gemini = ler_documento_gemini(
                                    arquivo_bytes,
                                    arquivo.name,
                                    api_key_gemini,
                                    timeout=timeout_gemini,
                                    campos_alvo=alvos_chamada
                                )

                                dados = _mesclar_gemini(
                                    dados,
                                    retorno_gemini["dados"],
                                    alvos_chamada
                                )

                                _registrar_gemini(retorno_gemini["uso"])
                                _monitor_gemini(gemini_area)

                                if criticos and "nome_mae" in campos_alvo:
                                    consumo = _consumo_gemini()
                                    permitido_mae, _ = pode_chamar_gemini(
                                        consumo["documentos"],
                                        consumo["custo_brl"]
                                    )

                                    if permitido_mae:
                                        try:
                                            retorno_mae = ler_documento_gemini(
                                                arquivo_bytes,
                                                arquivo.name,
                                                api_key_gemini,
                                                timeout=8,
                                                campos_alvo=["nome_mae"]
                                            )

                                            dados = _mesclar_gemini(
                                                dados,
                                                retorno_mae["dados"],
                                                ["nome_mae"]
                                            )

                                            _registrar_gemini(
                                                retorno_mae["uso"]
                                            )
                                            _monitor_gemini(
                                                gemini_area
                                            )
                                        except Exception:
                                            pass

                            except Exception as erro_gemini:
                                st.caption(
                                    f"⚠️ Gemini não completou {arquivo.name}: "
                                    f"{erro_gemini}"
                                )
                        else:
                            st.caption(
                                f"🔒 Gemini pausado: {motivo}"
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

                    # Protege imediatamente o documento já processado.
                    # Se o Streamlit cair daqui para frente, este resultado
                    # poderá ser recuperado sem novo OCR/Gemini.
                    if resultados:
                        sheets.salvar_rascunho_item(
                            webhook_url,
                            st.session_state.get("lote_persistente_id", ""),
                            resultados[-1],
                            supervisor,
                            sub,
                            comunidade
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

                # Salva esta conferência imediatamente no rascunho persistente.
                # Assim as correções já confirmadas não somem se a sessão cair.
                if st.button(
                    "💾 Salvar correção deste cadastro",
                    key=f"salvar_rascunho_{indice_item}_{arquivo_item}"
                ):
                    retorno_rascunho = sheets.salvar_rascunho_item(
                        webhook_url,
                        st.session_state.get("lote_persistente_id", ""),
                        item,
                        supervisor,
                        sub,
                        comunidade
                    )
                    if retorno_rascunho.get("sucesso"):
                        st.success("Correção protegida.")
                    else:
                        st.error(retorno_rascunho.get(
                            "mensagem",
                            "Não foi possível proteger a correção."
                        ))

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
                lote_finalizado_id = st.session_state.get(
                    "lote_persistente_id", ""
                )
                if lote_finalizado_id:
                    sheets.excluir_rascunho_lote(
                        webhook_url,
                        lote_finalizado_id
                    )

                st.session_state.pop("resultado_lote", None)
                st.session_state.pop("lote_persistente_id", None)
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
