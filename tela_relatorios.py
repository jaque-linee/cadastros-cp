import base64

import streamlit as st
import pandas as pd
import streamlit.components.v1 as components

import relatorios


def exibir_tela_relatorios(base):
    """Exibe a interface completa de relatórios do Sistema de Cadastro CP."""
    st.subheader("📊 Relatórios")
    st.caption("Consulte a base cadastrada de forma rápida e organizada.")

    tipo_relatorio = st.selectbox(
        "Tipo de relatório",
        ["👤 Por Nome", "📍 Por Zona", "🏠 Por Domicílio", "🔀 Cruzamentos"],
        key="tipo_relatorio"
    )

    # ============================================================
    # RELATÓRIO POR NOME
    # ============================================================
    if tipo_relatorio == "👤 Por Nome":
        filtros_disponiveis = relatorios.obter_filtros_nome(base)

        col_filtro_sup, col_filtro_sub, col_filtro_sit = st.columns(3)

        with col_filtro_sup:
            filtro_supervisor = st.selectbox(
                "Supervisor",
                ["Todos"] + filtros_disponiveis.get("supervisores", []),
                key="relatorio_nome_supervisor"
            )

        with col_filtro_sub:
            filtro_subsupervisor = st.selectbox(
                "Subsupervisor",
                ["Todos"] + filtros_disponiveis.get("subsupervisores", []),
                key="relatorio_nome_subsupervisor"
            )

        with col_filtro_sit:
            filtro_situacao = st.selectbox(
                "Situação",
                ["Todas"] + filtros_disponiveis.get("situacoes", []),
                key="relatorio_nome_situacao"
            )

        gerar_relatorio = st.button("🔎 Gerar relatório", type="primary", use_container_width=True, key="gerar_relatorio_nome")

        if gerar_relatorio:
            st.session_state["relatorio_nome_gerado"] = relatorios.gerar_relatorio_nome(
                dados_base=base,
                supervisor="" if filtro_supervisor == "Todos" else filtro_supervisor,
                subsupervisor="" if filtro_subsupervisor == "Todos" else filtro_subsupervisor,
                situacao="" if filtro_situacao == "Todas" else filtro_situacao
            )

        resultado_relatorio = st.session_state.get("relatorio_nome_gerado")

        if resultado_relatorio is not None:
            total_relatorio = resultado_relatorio.get("total", 0)

            st.markdown(
                f"""
                <div style="background:#ffffff;border:1px solid #d9e1e8;border-radius:10px;padding:10px 14px;margin:14px 0 12px 0;font-size:0.95rem;">
                    <b>👤 Relatório por Nome</b> &nbsp;&nbsp; <b>{total_relatorio}</b> registro(s)
                </div>
                """,
                unsafe_allow_html=True
            )

            if total_relatorio == 0:
                st.info("Nenhum cadastro encontrado para os filtros selecionados.")
            else:
                for grupo in resultado_relatorio.get("grupos", []):
                    nome_supervisor = str(grupo.get("supervisor", "SEM SUPERVISOR")).strip()
                    nome_subsupervisor = str(grupo.get("subsupervisor", "SEM SUBSUPERVISOR")).strip()
                    registros_grupo = grupo.get("registros", [])

                    st.markdown(
                        f"""
                        <div style="background:#f7f9fb;border-left:4px solid #0056b3;padding:8px 12px;margin-top:12px;margin-bottom:6px;border-radius:6px;">
                            <b>Supervisor:</b> {nome_supervisor} &nbsp;&nbsp;&nbsp; <b>Subsupervisor:</b> {nome_subsupervisor} &nbsp;&nbsp;&nbsp; <b>Total:</b> {len(registros_grupo)}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    linhas_tabela = []
                    for numero, registro in enumerate(registros_grupo, start=1):
                        linhas_tabela.append({
                            "Nº": numero,
                            "Nome": str(registro.get("nome", "")).strip(),
                            "Comunidade": str(registro.get("comunidade", "")).strip(),
                            "Telefone": str(registro.get("telefone", "")).strip()
                        })

                    tabela_grupo = pd.DataFrame(linhas_tabela)
                    st.dataframe(tabela_grupo, use_container_width=True, hide_index=True, height=min(38 * len(tabela_grupo) + 38, 500))

            if total_relatorio > 0:
                try:
                    pdf_relatorio = relatorios.gerar_pdf_relatorio_nome(resultado_relatorio)

                    coluna_imprimir, coluna_pdf = st.columns(2)

                    with coluna_imprimir:
                        pdf_base64 = base64.b64encode(pdf_relatorio).decode("utf-8")
                        components.html(
                            f"""
                            <button onclick="imprimirPDFNome()" style="width:100%;height:38px;background:#0056b3;color:white;border:2px solid #0056b3;border-radius:12px;font-weight:bold;cursor:pointer;font-family:sans-serif;">🖨️ Imprimir</button>
                            <script>
                            function imprimirPDFNome() {{
                                const base64 = "{pdf_base64}";
                                const binario = atob(base64);
                                const bytes = new Uint8Array(binario.length);
                                for (let i = 0; i < binario.length; i++) {{
                                    bytes[i] = binario.charCodeAt(i);
                                }}
                                const blob = new Blob([bytes], {{type: "application/pdf"}});
                                const url = URL.createObjectURL(blob);
                                const janela = window.open(url, "_blank", "width=1000,height=800");
                                if (!janela) {{
                                    alert("O navegador bloqueou o pop-up. Permita pop-ups para este site.");
                                    return;
                                }}
                                setTimeout(function() {{
                                    try {{
                                        janela.focus();
                                        janela.print();
                                    }} catch (e) {{
                                    }}
                                }}, 1200);
                            }}
                            </script>
                            """,
                            height=45,
                            scrolling=False
                        )

                    with coluna_pdf:
                        st.download_button(
                            label="📄 Baixar PDF",
                            data=pdf_relatorio,
                            file_name="relatorio_por_nome.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key="baixar_pdf_relatorio_nome"
                        )

                except Exception as erro_pdf:
                    st.error(f"Não foi possível gerar o PDF: {erro_pdf}")

    # ============================================================
    # RELATÓRIO POR ZONA
    # ============================================================
    elif tipo_relatorio == "📍 Por Zona":
        filtros_disponiveis = relatorios.obter_filtros_zona(base)

        col_sup, col_sub, col_sit = st.columns(3)

        with col_sup:
            filtro_supervisor = st.selectbox(
                "Supervisor",
                ["Todos"] + filtros_disponiveis.get("supervisores", []),
                key="relatorio_zona_supervisor"
            )

        with col_sub:
            filtro_subsupervisor = st.selectbox(
                "Subsupervisor",
                ["Todos"] + filtros_disponiveis.get("subsupervisores", []),
                key="relatorio_zona_subsupervisor"
            )

        with col_sit:
            filtro_situacao = st.selectbox(
                "Situação",
                ["Todas"] + filtros_disponiveis.get("situacoes", []),
                key="relatorio_zona_situacao"
            )

        col_zona, col_secao = st.columns(2)

        with col_zona:
            filtro_zona = st.selectbox(
                "Zona",
                ["Todas"] + filtros_disponiveis.get("zonas", []),
                key="relatorio_zona_zona"
            )

        secoes_disponiveis = relatorios.obter_secoes_por_zona(base, "" if filtro_zona == "Todas" else filtro_zona)

        with col_secao:
            filtro_secao = st.selectbox(
                "Seção",
                ["Todas"] + secoes_disponiveis,
                key="relatorio_zona_secao"
            )

        gerar_relatorio_zona = st.button("🔎 Gerar relatório", type="primary", use_container_width=True, key="gerar_relatorio_zona")

        if gerar_relatorio_zona:
            st.session_state["relatorio_zona_gerado"] = relatorios.gerar_relatorio_zona(
                dados_base=base,
                supervisor="" if filtro_supervisor == "Todos" else filtro_supervisor,
                subsupervisor="" if filtro_subsupervisor == "Todos" else filtro_subsupervisor,
                zona="" if filtro_zona == "Todas" else filtro_zona,
                secao="" if filtro_secao == "Todas" else filtro_secao,
                situacao="" if filtro_situacao == "Todas" else filtro_situacao
            )

        resultado_zona = st.session_state.get("relatorio_zona_gerado")

        if resultado_zona is not None:
            total = resultado_zona.get("total", 0)
            total_zonas = resultado_zona.get("total_zonas", 0)
            total_secoes = resultado_zona.get("total_secoes", 0)

            st.markdown(
                f"""
                <div style="background:#ffffff;border:1px solid #d9e1e8;border-radius:10px;padding:10px 14px;margin:14px 0 12px 0;font-size:0.95rem;">
                    <b>📍 Relatório por Zona</b> &nbsp;&nbsp; <b>{total}</b> registro(s) &nbsp;&nbsp; <b>{total_zonas}</b> zona(s) &nbsp;&nbsp; <b>{total_secoes}</b> seção(ões)
                </div>
                """,
                unsafe_allow_html=True
            )

            if total == 0:
                st.info("Nenhum cadastro encontrado para os filtros selecionados.")
            else:
                linhas = []
                for numero, registro in enumerate(resultado_zona.get("registros", []), start=1):
                    linhas.append({
                        "Nº": numero,
                        "Zona": registro.get("zona", ""),
                        "Seção": registro.get("secao", ""),
                        "Nome": registro.get("nome", ""),
                        "Comunidade": registro.get("comunidade", ""),
                        "Telefone": registro.get("telefone", "")
                    })

                tabela_zona = pd.DataFrame(linhas)
                st.dataframe(tabela_zona, use_container_width=True, hide_index=True, height=min(38 * len(tabela_zona) + 38, 600))

                st.markdown("#### Resumo por Zona e Seção")

                resumo_linhas = []
                for grupo in resultado_zona.get("resumo", []):
                    zona_atual = grupo.get("zona", "")
                    for item in grupo.get("secoes", []):
                        resumo_linhas.append({
                            "Zona": zona_atual,
                            "Seção": item.get("secao", ""),
                            "Quantidade": item.get("total", 0)
                        })
                    resumo_linhas.append({
                        "Zona": f"TOTAL ZONA {zona_atual}",
                        "Seção": "",
                        "Quantidade": grupo.get("total", 0)
                    })

                resumo_linhas.append({
                    "Zona": "TOTAL GERAL",
                    "Seção": "",
                    "Quantidade": total
                })

                st.dataframe(pd.DataFrame(resumo_linhas), use_container_width=True, hide_index=True)

                try:
                    pdf_relatorio_zona = relatorios.gerar_pdf_relatorio_zona(resultado_zona)

                    coluna_imprimir, coluna_pdf = st.columns(2)

                    with coluna_imprimir:
                        pdf_base64_zona = base64.b64encode(pdf_relatorio_zona).decode("utf-8")
                        components.html(
                            f"""
                            <button onclick="imprimirPDFZona()" style="width:100%;height:38px;background:#0056b3;color:white;border:2px solid #0056b3;border-radius:12px;font-weight:bold;cursor:pointer;font-family:sans-serif;">🖨️ Imprimir</button>
                            <script>
                            function imprimirPDFZona() {{
                                const base64 = "{pdf_base64_zona}";
                                const binario = atob(base64);
                                const bytes = new Uint8Array(binario.length);
                                for (let i = 0; i < binario.length; i++) {{
                                    bytes[i] = binario.charCodeAt(i);
                                }}
                                const blob = new Blob([bytes], {{type: "application/pdf"}});
                                const url = URL.createObjectURL(blob);
                                const janela = window.open(url, "_blank", "width=1000,height=800");
                                if (!janela) {{
                                    alert("O navegador bloqueou o pop-up. Permita pop-ups para este site.");
                                    return;
                                }}
                                setTimeout(function() {{
                                    try {{
                                        janela.focus();
                                        janela.print();
                                    }} catch (e) {{
                                    }}
                                }}, 1200);
                            }}
                            </script>
                            """,
                            height=45,
                            scrolling=False
                        )

                    with coluna_pdf:
                        st.download_button(
                            label="📄 Baixar PDF",
                            data=pdf_relatorio_zona,
                            file_name="relatorio_por_zona.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key="baixar_pdf_relatorio_zona"
                        )

                except Exception as erro_pdf:
                    st.error(f"Não foi possível gerar o PDF: {erro_pdf}")

    # ============================================================
    # RELATÓRIO POR DOMICÍLIO
    # ============================================================
    elif tipo_relatorio == "🏠 Por Domicílio":
        filtros_disponiveis = relatorios.obter_filtros_domicilio(base)

        col_sup, col_sub = st.columns(2)

        with col_sup:
            filtro_supervisor = st.selectbox(
                "Supervisor",
                ["Todos"] + filtros_disponiveis.get("supervisores", []),
                key="relatorio_domicilio_supervisor"
            )

        with col_sub:
            filtro_subsupervisor = st.selectbox(
                "Subsupervisor",
                ["Todos"] + filtros_disponiveis.get("subsupervisores", []),
                key="relatorio_domicilio_subsupervisor"
            )

        col_dom, col_sit = st.columns(2)

        with col_dom:
            filtro_domicilio = st.selectbox(
                "Domicílio",
                ["Todos"] + filtros_disponiveis.get("domicilios", []),
                key="relatorio_domicilio_domicilio"
            )

        with col_sit:
            filtro_situacao = st.selectbox(
                "Situação",
                ["Todas"] + filtros_disponiveis.get("situacoes", []),
                key="relatorio_domicilio_situacao"
            )

        gerar_relatorio_domicilio = st.button("🔎 Gerar relatório", type="primary", use_container_width=True, key="gerar_relatorio_domicilio")

        if gerar_relatorio_domicilio:
            st.session_state["relatorio_domicilio_gerado"] = relatorios.gerar_relatorio_domicilio(
                dados_base=base,
                supervisor="" if filtro_supervisor == "Todos" else filtro_supervisor,
                subsupervisor="" if filtro_subsupervisor == "Todos" else filtro_subsupervisor,
                domicilio="" if filtro_domicilio == "Todos" else filtro_domicilio,
                situacao="" if filtro_situacao == "Todas" else filtro_situacao
            )

        resultado_domicilio = st.session_state.get("relatorio_domicilio_gerado")

        if resultado_domicilio is not None:
            total = resultado_domicilio.get("total", 0)
            total_domicilios = resultado_domicilio.get("total_domicilios", 0)

            st.markdown(
                f"""
                <div style="background:#ffffff;border:1px solid #d9e1e8;border-radius:10px;padding:10px 14px;margin:14px 0 12px 0;font-size:0.95rem;">
                    <b>🏠 Relatório por Domicílio</b> &nbsp;&nbsp; <b>{total}</b> registro(s) &nbsp;&nbsp; <b>{total_domicilios}</b> domicílio(s)
                </div>
                """,
                unsafe_allow_html=True
            )

            if total == 0:
                st.info("Nenhum cadastro encontrado para os filtros selecionados.")
            else:
                linhas = []
                for numero, registro in enumerate(resultado_domicilio.get("registros", []), start=1):
                    linhas.append({
                        "Nº": numero,
                        "Domicílio": registro.get("domicilio", ""),
                        "Nome": registro.get("nome", ""),
                        "Comunidade": registro.get("comunidade", ""),
                        "Telefone": registro.get("telefone", "")
                    })

                tabela_domicilio = pd.DataFrame(linhas)
                st.dataframe(tabela_domicilio, use_container_width=True, hide_index=True, height=min(38 * len(tabela_domicilio) + 38, 600))

                st.markdown("#### Resumo por Domicílio")

                resumo_linhas = []
                for item in resultado_domicilio.get("resumo", []):
                    resumo_linhas.append({
                        "Domicílio": item.get("domicilio", ""),
                        "Quantidade": item.get("total", 0)
                    })

                resumo_linhas.append({
                    "Domicílio": "TOTAL GERAL",
                    "Quantidade": total
                })

                st.dataframe(pd.DataFrame(resumo_linhas), use_container_width=True, hide_index=True)

                try:
                    pdf_relatorio_domicilio = relatorios.gerar_pdf_relatorio_domicilio(resultado_domicilio)

                    coluna_imprimir, coluna_pdf = st.columns(2)

                    with coluna_imprimir:
                        pdf_base64_domicilio = base64.b64encode(pdf_relatorio_domicilio).decode("utf-8")
                        components.html(
                            f"""
                            <button onclick="imprimirPDFDomicilio()" style="width:100%;height:38px;background:#0056b3;color:white;border:2px solid #0056b3;border-radius:12px;font-weight:bold;cursor:pointer;font-family:sans-serif;">🖨️ Imprimir</button>
                            <script>
                            function imprimirPDFDomicilio() {{
                                const base64 = "{pdf_base64_domicilio}";
                                const binario = atob(base64);
                                const bytes = new Uint8Array(binario.length);
                                for (let i = 0; i < binario.length; i++) {{
                                    bytes[i] = binario.charCodeAt(i);
                                }}
                                const blob = new Blob([bytes], {{type: "application/pdf"}});
                                const url = URL.createObjectURL(blob);
                                const janela = window.open(url, "_blank", "width=1000,height=800");
                                if (!janela) {{
                                    alert("O navegador bloqueou o pop-up. Permita pop-ups para este site.");
                                    return;
                                }}
                                setTimeout(function() {{
                                    try {{
                                        janela.focus();
                                        janela.print();
                                    }} catch (e) {{
                                    }}
                                }}, 1200);
                            }}
                            </script>
                            """,
                            height=45,
                            scrolling=False
                        )

                    with coluna_pdf:
                        st.download_button(
                            label="📄 Baixar PDF",
                            data=pdf_relatorio_domicilio,
                            file_name="relatorio_por_domicilio.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key="baixar_pdf_relatorio_domicilio"
                        )

                except Exception as erro_pdf:
                    st.error(f"Não foi possível gerar o PDF: {erro_pdf}")

    # ============================================================
    # RELATÓRIO DE CRUZAMENTOS
    # ============================================================
    elif tipo_relatorio == "🔀 Cruzamentos":
        consulta_concorrentes = sheets.carregar_concorrentes(WEBHOOK_URL)

        if not consulta_concorrentes.get("sucesso"):
            st.error(consulta_concorrentes.get("mensagem", "Não foi possível carregar as bases concorrentes."))
        else:
            bases_concorrentes = consulta_concorrentes.get("dados", {})

            filtros_disponiveis = relatorios.obter_filtros_cruzamentos(base, bases_concorrentes)

            col_sup, col_sub, col_sit = st.columns(3)

            with col_sup:
                filtro_supervisor = st.selectbox(
                    "Supervisor",
                    ["Todos"] + filtros_disponiveis.get("supervisores", []),
                    key="relatorio_cruzamentos_supervisor"
                )

            with col_sub:
                filtro_subsupervisor = st.selectbox(
                    "Subsupervisor",
                    ["Todos"] + filtros_disponiveis.get("subsupervisores", []),
                    key="relatorio_cruzamentos_subsupervisor"
                )

            with col_sit:
                filtro_situacao = st.selectbox(
                    "Situação",
                    ["Todas"] + filtros_disponiveis.get("situacoes", []),
                    key="relatorio_cruzamentos_situacao"
                )

            col_base, col_resultado = st.columns(2)

            with col_base:
                filtro_base_cruzada = st.selectbox(
                    "Base cruzada",
                    ["Todas"] + filtros_disponiveis.get("bases", []),
                    key="relatorio_cruzamentos_base"
                )

            with col_resultado:
                filtro_resultado_cruzamento = st.selectbox(
                    "Resultado",
                    ["Todos", "Cruzou", "Não cruzou"],
                    key="relatorio_cruzamentos_resultado"
                )

            gerar_cruzamentos = st.button("🔎 Gerar relatório", type="primary", use_container_width=True, key="gerar_relatorio_cruzamentos")

            if gerar_cruzamentos:
                st.session_state["relatorio_cruzamentos_gerado"] = relatorios.gerar_relatorio_cruzamentos(
                    dados_base=base,
                    bases_concorrentes=bases_concorrentes,
                    supervisor="" if filtro_supervisor == "Todos" else filtro_supervisor,
                    subsupervisor="" if filtro_subsupervisor == "Todos" else filtro_subsupervisor,
                    situacao="" if filtro_situacao == "Todas" else filtro_situacao,
                    base_cruzada="" if filtro_base_cruzada == "Todas" else filtro_base_cruzada,
                    resultado_cruzamento="" if filtro_resultado_cruzamento == "Todos" else filtro_resultado_cruzamento
                )

            resultado_cruzamentos = st.session_state.get("relatorio_cruzamentos_gerado")

            if resultado_cruzamentos is not None:
                total = resultado_cruzamentos.get("total", 0)
                total_com = resultado_cruzamentos.get("total_com_cruzamento", 0)
                total_sem = resultado_cruzamentos.get("total_sem_cruzamento", 0)

                st.markdown(
                    f"""
                    <div style="background:#ffffff;border:1px solid #d9e1e8;border-radius:10px;padding:10px 14px;margin:14px 0 12px 0;font-size:0.95rem;">
                        <b>🔀 Relatório de Cruzamentos</b> &nbsp;&nbsp; <b>{total}</b> registro(s) &nbsp;&nbsp; <b>{total_com}</b> com cruzamento &nbsp;&nbsp; <b>{total_sem}</b> sem cruzamento
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if total == 0:
                    st.info("Nenhum cadastro encontrado para os filtros selecionados.")
                else:
                    for grupo in resultado_cruzamentos.get("grupos", []):
                        nome_supervisor = str(grupo.get("supervisor", "SEM SUPERVISOR")).strip()
                        nome_subsupervisor = str(grupo.get("subsupervisor", "SEM SUBSUPERVISOR")).strip()
                        registros_grupo = grupo.get("registros", [])

                        st.markdown(
                            f"""
                            <div style="background:#f7f9fb;border-left:4px solid #0056b3;padding:8px 12px;margin-top:12px;margin-bottom:6px;border-radius:6px;">
                                <b>Supervisor:</b> {nome_supervisor} &nbsp;&nbsp;&nbsp; <b>Subsupervisor:</b> {nome_subsupervisor} &nbsp;&nbsp;&nbsp; <b>Total:</b> {len(registros_grupo)}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                        linhas_tabela = []
                        for numero, registro in enumerate(registros_grupo, start=1):
                            cruzou = bool(registro.get("cruzou_alguma"))
                            marcador = "●" if cruzou else ""
                            cruzamentos_texto = registro.get("cruzamentos_texto", "") or "—"

                            linhas_tabela.append({
                                "●": marcador,
                                "Nº": str(numero),
                                "Nome": registro.get("nome", ""),
                                "Comunidade": registro.get("comunidade", ""),
                                "Telefone": registro.get("telefone", ""),
                                "Cruzamentos": cruzamentos_texto
                            })

                        st.dataframe(
                            pd.DataFrame(linhas_tabela),
                            use_container_width=True,
                            hide_index=True,
                            height=min(38 * len(linhas_tabela) + 38, 600),
                            column_config={
                                "●": st.column_config.TextColumn("", width="small"),
                                "Nº": st.column_config.TextColumn("Nº", width="small"),
                                "Nome": st.column_config.TextColumn("Nome", width="large"),
                                "Comunidade": st.column_config.TextColumn("Comunidade", width="medium"),
                                "Telefone": st.column_config.TextColumn("Telefone", width="medium"),
                                "Cruzamentos": st.column_config.TextColumn("Cruzamentos", width="large")
                            }
                        )

                    st.markdown("#### Resumo dos Cruzamentos")

                    resumo_linhas = []
                    for item in resultado_cruzamentos.get("resumo_bases", []):
                        resumo_linhas.append({
                            "Base": item.get("base", ""),
                            "Cruzaram": item.get("cruzaram", 0),
                            "Não cruzaram": item.get("nao_cruzaram", 0)
                        })

                    st.dataframe(pd.DataFrame(resumo_linhas), use_container_width=True, hide_index=True)

                    st.caption(f"Com cruzamento em pelo menos uma base: {total_com} | Sem cruzamento em nenhuma base: {total_sem} | Total: {total}")

                    try:
                        pdf_cruzamentos = relatorios.gerar_pdf_relatorio_cruzamentos(resultado_cruzamentos)

                        coluna_imprimir, coluna_pdf = st.columns(2)

                        with coluna_imprimir:
                            pdf_base64_cruzamentos = base64.b64encode(pdf_cruzamentos).decode("utf-8")
                            components.html(
                                f"""
                                <button onclick="imprimirPDFCruzamentos()" style="width:100%;height:38px;background:#0056b3;color:white;border:2px solid #0056b3;border-radius:12px;font-weight:bold;cursor:pointer;font-family:sans-serif;">🖨️ Imprimir</button>
                                <script>
                                function imprimirPDFCruzamentos() {{
                                    const base64 = "{pdf_base64_cruzamentos}";
                                    const binario = atob(base64);
                                    const bytes = new Uint8Array(binario.length);
                                    for (let i = 0; i < binario.length; i++) {{
                                        bytes[i] = binario.charCodeAt(i);
                                    }}
                                    const blob = new Blob([bytes], {{type: "application/pdf"}});
                                    const url = URL.createObjectURL(blob);
                                    const janela = window.open(url, "_blank", "width=1000,height=800");
                                    if (!janela) {{
                                        alert("O navegador bloqueou o pop-up. Permita pop-ups para este site.");
                                        return;
                                    }}
                                    setTimeout(function() {{
                                        try {{
                                            janela.focus();
                                            janela.print();
                                        }} catch (e) {{
                                        }}
                                    }}, 1200);
                                }}
                                </script>
                                """,
                                height=45,
                                scrolling=False
                            )

                        with coluna_pdf:
                            st.download_button(
                                label="📄 Baixar PDF",
                                data=pdf_cruzamentos,
                                file_name="relatorio_de_cruzamentos.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                key="baixar_pdf_relatorio_cruzamentos"
                            )

                    except Exception as erro_pdf:
                        st.error(f"Não foi possível gerar o PDF: {erro_pdf}")
