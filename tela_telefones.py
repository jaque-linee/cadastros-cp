import re
import streamlit as st
import sheets


def _texto(valor):
    return str(valor or "").strip()


def _upper(valor):
    return _texto(valor).upper()


def formatar_telefone(valor):
    numeros = re.sub(r"\D", "", _texto(valor))
    if numeros.startswith("55") and len(numeros) in (12, 13):
        numeros = numeros[2:]
    if len(numeros) == 11:
        return f"({numeros[:2]}) {numeros[2:7]}-{numeros[7:]}"
    if len(numeros) == 10:
        return f"({numeros[:2]}) {numeros[2:6]}-{numeros[6:]}"
    return _texto(valor)


def telefone_valido(valor):
    numeros = re.sub(r"\D", "", _texto(valor))
    if numeros.startswith("55") and len(numeros) in (12, 13):
        numeros = numeros[2:]
    return len(numeros) in (10, 11)


def exibir_tela_telefones(base, webhook_url):
    st.subheader("📱 Atualização de Telefones")
    st.caption("Mostra somente cadastros com SITUAÇÃO R e TELEFONE vazio.")

    elegiveis = [
        p for p in (base or [])
        if _upper(p.get("situacao")) == "R"
        and not _texto(p.get("telefone"))
    ]

    if not elegiveis:
        st.success("Não há cadastros com SITUAÇÃO R e telefone vazio.")
        return

    supervisores = sorted({_upper(p.get("supervisor")) for p in elegiveis if _upper(p.get("supervisor"))})
    if not supervisores:
        st.info("Não encontrei supervisores entre os cadastros pendentes.")
        return

    supervisor = st.selectbox("Supervisor", supervisores, key="tel_supervisor")

    do_supervisor = [p for p in elegiveis if _upper(p.get("supervisor")) == supervisor]
    subs = sorted({_upper(p.get("subsupervisor")) or "SEM SUBSUPERVISOR" for p in do_supervisor})
    sub = st.selectbox("Subsupervisor", subs, key="tel_subsupervisor")

    pendentes = [
        p for p in do_supervisor
        if (_upper(p.get("subsupervisor")) or "SEM SUBSUPERVISOR") == sub
    ]

    st.info(f"📌 {len(pendentes)} telefone(s) pendente(s) neste Supervisor/Sub.")

    if not pendentes:
        return

    preenchidos = []

    for i, pessoa in enumerate(pendentes):
        nome = _texto(pessoa.get("nome")) or "NOME NÃO INFORMADO"
        comunidade = _texto(pessoa.get("comunidade"))
        titulo = _texto(pessoa.get("titulo"))
        cpf = _texto(pessoa.get("cpf"))

        st.markdown(f"**{i + 1}. {nome}**")
        detalhes = []
        if comunidade:
            detalhes.append(f"Comunidade: {comunidade}")
        if titulo:
            detalhes.append(f"Título: {titulo}")
        if cpf:
            detalhes.append(f"CPF: {cpf}")
        if detalhes:
            st.caption(" • ".join(detalhes))

        valor = st.text_input(
            "Telefone",
            key=f"telefone_pendente_{supervisor}_{sub}_{i}_{titulo}_{cpf}",
            placeholder="(82) 99999-9999",
            max_chars=16,
        )

        if _texto(valor):
            if telefone_valido(valor):
                preenchidos.append({
                    "nome": nome,
                    "titulo": titulo,
                    "cpf": cpf,
                    "telefone": formatar_telefone(valor),
                })
            else:
                st.warning(f"Telefone inválido para {nome}. Digite DDD + número.")

        st.markdown("<div style='border-bottom:1px solid #d9e1e8; margin:2px 0 10px 0;'></div>", unsafe_allow_html=True)

    st.caption(f"Preenchidos agora: {len(preenchidos)} de {len(pendentes)}")

    if preenchidos:
        if st.button("💾 Salvar telefones preenchidos", type="primary", use_container_width=True):
            ok = 0
            erros = []
            progresso = st.progress(0)

            for indice, item in enumerate(preenchidos):
                retorno = sheets.atualizar_telefone(
                    webhook_url,
                    telefone=item["telefone"],
                    titulo=item["titulo"],
                    cpf=item["cpf"],
                )
                if retorno.get("sucesso"):
                    ok += 1
                else:
                    erros.append(f"{item['nome']}: {retorno.get('mensagem', 'Erro ao atualizar.')}")
                progresso.progress((indice + 1) / len(preenchidos))

            if ok:
                st.success(f"✅ {ok} telefone(s) atualizado(s).")
            for erro in erros:
                st.error(erro)

            if ok:
                st.cache_data.clear()
                st.rerun()
