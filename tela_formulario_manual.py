import streamlit as st
import requests
import re
import html

import sheets


def somente_numeros(valor):
    return re.sub(r"\D", "", str(valor or ""))


def _texto(valor, padrao="-"):
    valor = str(valor or "").strip()
    return valor if valor else padrao


def _esc(valor, padrao="-"):
    return html.escape(_texto(valor, padrao))


def _cpf_formatado(valor):
    n = somente_numeros(valor)
    if len(n) == 11:
        return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"
    return _texto(valor)


def _limpar_busca_manual():
    st.session_state.busca_realizada = False
    st.session_state.encontrado = None
    st.session_state.titulo = ""
    st.session_state["bases_encontradas_manual"] = []


def _mostrar_cadastro_encontrado(e):
    familia = (
        e.get("id_familia")
        or e.get("ID FAMÍLIA")
        or e.get("ID FAMILIA")
        or ""
    )

    v = {
        "nome": _esc(e.get("nome")),
        "supervisor": _esc(e.get("supervisor")),
        "sub": _esc(e.get("subsupervisor")),
        "familia": _esc(familia),
        "situacao": _esc(e.get("situacao")),
        "status": _esc(e.get("status")),
        "entrega": _esc(e.get("data_entrega")),
        "titulo": _esc(e.get("titulo")),
        "cpf": _esc(_cpf_formatado(e.get("cpf"))),
        "rg": _esc(e.get("rg")),
        "nascimento": _esc(e.get("data_nascimento")),
        "mae": _esc(e.get("nome_mae")),
        "endereco": _esc(e.get("endereco")),
        "numero": _esc(e.get("numero")),
        "bairro": _esc(e.get("bairro")),
        "cidade": _esc(e.get("cidade")),
        "comunidade": _esc(e.get("comunidade")),
        "telefone": _esc(e.get("telefone")),
        "zona": _esc(e.get("zona")),
        "secao": _esc(e.get("secao")),
        "domicilio": _esc(e.get("domicilio")),
    }

    st.markdown("""
<style>
.base-card{border:1px solid #efb5ba;background:#fff7f7;border-radius:14px;padding:20px;margin:8px 0 14px}
.base-top{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:16px}
.base-alert{color:#c62828;font-weight:800;font-size:1.05rem;margin-bottom:7px}
.base-name{color:#172b4d;font-size:1.35rem;font-weight:800;line-height:1.2}
.base-sub{margin-top:7px;color:#334155;font-size:.95rem}
.base-status{text-align:right;color:#475569;font-size:.9rem;line-height:1.55;white-space:nowrap}
.base-pill{display:inline-block;padding:4px 12px;border-radius:999px;background:#ffd9dd;color:#b4232d;font-weight:700;margin-bottom:5px}
.base-grid{display:grid;grid-template-columns:1.7fr 1fr;gap:14px}
.base-box{background:white;border:1px solid #e5e7eb;border-radius:12px;padding:15px 16px}
.base-box-title{font-size:1.03rem;font-weight:800;color:#172b4d;background:#eef6ff;border-radius:8px;padding:8px 10px;margin-bottom:13px}
.base-vote-title{background:#fff7d9}
.base-data-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px 22px;color:#334155;font-size:.92rem}
.base-data-grid b{color:#172b4d}
.base-local{font-size:1.08rem;font-weight:800;color:#172b4d;line-height:1.35;margin:8px 0 15px}
.base-vote-grid{display:grid;grid-template-columns:repeat(3,1fr);text-align:center;background:#f8fafc;border-radius:10px;padding:10px 4px;gap:2px}
.base-vote-grid div+div{border-left:1px solid #d8dee8}
.base-vote-label{display:block;color:#64748b;font-size:.78rem;margin-bottom:3px}
.base-vote-value{color:#172b4d;font-size:1rem;font-weight:800}
@media(max-width:800px){.base-grid,.base-data-grid{grid-template-columns:1fr}.base-top{display:block}.base-status{text-align:left;margin-top:12px;white-space:normal}}
</style>
""", unsafe_allow_html=True)

    painel = f"""
<div class="base-card">
 <div class="base-top">
  <div>
   <div class="base-alert">⚠️ Já cadastrado na BASE</div>
   <div class="base-name">{v['nome']}</div>
   <div class="base-sub">Supervisor: <b>{v['supervisor']}</b> &nbsp;|&nbsp; Subsupervisor: <b>{v['sub']}</b> &nbsp;|&nbsp; Família: <b>{v['familia']}</b></div>
  </div>
  <div class="base-status"><span class="base-pill">Situação: {v['situacao']}</span><br>Status: <b>{v['status']}</b><br>Data de entrega: <b>{v['entrega']}</b></div>
 </div>
 <div class="base-grid">
  <div class="base-box">
   <div class="base-box-title">🪪 Dados do Cadastro</div>
   <div class="base-data-grid">
    <div><b>Título:</b> {v['titulo']}</div><div><b>Comunidade:</b> {v['comunidade']}</div>
    <div><b>CPF:</b> {v['cpf']}</div><div><b>Endereço:</b> {v['endereco']}</div>
    <div><b>RG:</b> {v['rg']}</div><div><b>Nº:</b> {v['numero']}</div>
    <div><b>Data de nascimento:</b> {v['nascimento']}</div><div><b>Bairro:</b> {v['bairro']}</div>
    <div><b>Nome da mãe:</b> {v['mae']}</div><div><b>Cidade:</b> {v['cidade']}</div>
    <div><b>Telefone:</b> {v['telefone']}</div><div><b>ID Família:</b> {v['familia']}</div>
   </div>
  </div>
  <div class="base-box">
   <div class="base-box-title base-vote-title">📍 Local de Votação</div>
   <div class="base-local">{v['domicilio']}</div>
   <div class="base-vote-grid">
    <div><span class="base-vote-label">Zona</span><span class="base-vote-value">{v['zona']}</span></div>
    <div><span class="base-vote-label">Seção</span><span class="base-vote-value">{v['secao']}</span></div>
    <div><span class="base-vote-label">Município</span><span class="base-vote-value">{v['cidade']}</span></div>
   </div>
  </div>
 </div>
</div>
"""
    st.markdown(painel, unsafe_allow_html=True)


def exibir_tela_formulario_manual(base, webhook_url, supervisor, sub):
    """Exibe a consulta e o cadastro manual."""

    st.subheader("🔎 Consulta & Cadastro Manual")
    st.caption("Digite o número do título para consultar a BASE e os cruzamentos.")

    if "busca_realizada" not in st.session_state:
        st.session_state.update({
            "busca_realizada": False,
            "titulo": "",
            "encontrado": None,
            "bases_encontradas_manual": []
        })

    if "bases_encontradas_manual" not in st.session_state:
        st.session_state["bases_encontradas_manual"] = []

    c1, c2, c3 = st.columns([5.4, 1.35, 1.0])
    with c1:
        titulo_input = st.text_input(
            "Título de Eleitor:",
            value=st.session_state.titulo,
            placeholder="Digite somente os números"
        )
    with c2:
        st.write("")
        st.write("")
        pesquisar = st.button("🔍 Pesquisar", use_container_width=True, type="primary")
    with c3:
        st.write("")
        st.write("")
        limpar = st.button("🧹 Limpar", use_container_width=True)

    if limpar:
        _limpar_busca_manual()
        st.rerun()

    if pesquisar:
        st.session_state.titulo = titulo_input
        titulo_pesquisado = somente_numeros(titulo_input).lstrip("0")
        encontrado = None

        for pessoa in base:
            titulo_base = somente_numeros(pessoa.get("titulo", "")).lstrip("0")
            if titulo_pesquisado and titulo_base == titulo_pesquisado:
                encontrado = pessoa
                break

        st.session_state.encontrado = encontrado

        bases_encontradas = []
        consulta_concorrentes = sheets.carregar_concorrentes(webhook_url)

        if consulta_concorrentes.get("sucesso"):
            titulo_normalizado = somente_numeros(titulo_input).lstrip("0")
            for nome_base, titulos in consulta_concorrentes.get("dados", {}).items():
                titulos_normalizados = {
                    somente_numeros(t).lstrip("0")
                    for t in (titulos or [])
                    if somente_numeros(t)
                }
                if titulo_normalizado and titulo_normalizado in titulos_normalizados:
                    bases_encontradas.append(str(nome_base))

        st.session_state["bases_encontradas_manual"] = bases_encontradas
        st.session_state.busca_realizada = True

    if st.session_state.busca_realizada:
        bases_manual = st.session_state.get("bases_encontradas_manual", [])

        if bases_manual:
            st.success("🎯 Cruzamento encontrado: " + " | ".join(bases_manual))

        if st.session_state.encontrado:
            _mostrar_cadastro_encontrado(st.session_state.encontrado)

        else:
            st.success("Título não localizado na BASE. O cadastro pode ser realizado.")

            with st.form("cadastro_manual"):
                nome = st.text_input("Nome *")

                col1, col2 = st.columns(2)
                with col1:
                    cpf = st.text_input("CPF")
                with col2:
                    rg = st.text_input("RG")

                col3, col4 = st.columns(2)
                with col3:
                    data_nasc = st.text_input("Data de Nascimento (DD/MM/AAAA)")
                with col4:
                    telefone = st.text_input("Telefone")

                col5, col6, col7 = st.columns([2, 1, 1])
                with col5:
                    titulo_cadastro = st.text_input("Título", value=st.session_state.titulo)
                with col6:
                    zona = st.text_input("Zona")
                with col7:
                    secao = st.text_input("Seção")

                nome_mae = st.text_input("Nome da mãe")
                salvar = st.form_submit_button("💾 Salvar", type="primary")

                if salvar:
                    if not nome:
                        st.error("Informe o nome.")
                    else:
                        payload = {
                            "titulo": titulo_cadastro,
                            "nome": nome,
                            "cpf": cpf,
                            "rg": rg,
                            "data_nascimento": data_nasc,
                            "nome_mae": nome_mae,
                            "zona": zona,
                            "secao": secao,
                            "telefone": telefone,
                            "supervisor": supervisor,
                            "subsupervisor": sub
                        }
                        try:
                            resposta = requests.post(webhook_url, json=payload, timeout=30)
                            resultado = resposta.json()

                            if resultado.get("status") == "SUCESSO":
                                st.success("Salvo com sucesso!")
                                st.cache_data.clear()
                                _limpar_busca_manual()
                                st.rerun()
                            else:
                                st.error(resultado.get("mensagem", "Erro ao salvar."))
                        except Exception as erro:
                            st.error(f"Erro ao salvar: {erro}")


    # ============================================================
    # 28. RELATÓRIOS
    # ============================================================
