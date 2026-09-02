# ============================================================
# RELATÓRIOS
# ============================================================

from io import BytesIO
from datetime import datetime
import html
from cruzamento import buscar_titulo

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether
)


# ============================================================
# FUNÇÕES BÁSICAS
# ============================================================

def limpar_texto(valor):
    return str(
        valor or ""
    ).strip()


def normalizar_filtro(valor):
    return limpar_texto(
        valor
    ).upper()


# ============================================================
# LISTAS PARA OS FILTROS
# ============================================================

def obter_filtros_nome(dados_base):
    """
    Monta dinamicamente as opções disponíveis
    para o Relatório por Nome.

    Nenhuma coluna ou opção é fixada.
    """

    supervisores = set()
    subsupervisores = set()
    situacoes = set()

    for registro in dados_base or []:

        supervisor = limpar_texto(
            registro.get(
                "supervisor",
                ""
            )
        )

        subsupervisor = limpar_texto(
            registro.get(
                "subsupervisor",
                ""
            )
        )

        situacao = limpar_texto(
            registro.get(
                "situacao",
                ""
            )
        )

        if supervisor:
            supervisores.add(
                supervisor
            )

        if subsupervisor:
            subsupervisores.add(
                subsupervisor
            )

        if situacao:
            situacoes.add(
                situacao
            )

    return {
        "supervisores": sorted(
            supervisores,
            key=str.upper
        ),

        "subsupervisores": sorted(
            subsupervisores,
            key=str.upper
        ),

        "situacoes": sorted(
            situacoes,
            key=str.upper
        )
    }


# ============================================================
# FILTRAR RELATÓRIO POR NOME
# ============================================================

def filtrar_relatorio_nome(
    dados_base,
    supervisor="",
    subsupervisor="",
    situacao=""
):
    """
    Filtra a base por:

    - Supervisor
    - Subsupervisor
    - Situação

    Filtro vazio significa TODOS.
    """

    supervisor_filtro = normalizar_filtro(
        supervisor
    )

    subsupervisor_filtro = normalizar_filtro(
        subsupervisor
    )

    situacao_filtro = normalizar_filtro(
        situacao
    )

    registros = []

    for registro in dados_base or []:

        supervisor_registro = limpar_texto(
            registro.get(
                "supervisor",
                ""
            )
        )

        subsupervisor_registro = limpar_texto(
            registro.get(
                "subsupervisor",
                ""
            )
        )

        situacao_registro = limpar_texto(
            registro.get(
                "situacao",
                ""
            )
        )

        if (
            supervisor_filtro
            and normalizar_filtro(
                supervisor_registro
            ) != supervisor_filtro
        ):
            continue

        if (
            subsupervisor_filtro
            and normalizar_filtro(
                subsupervisor_registro
            ) != subsupervisor_filtro
        ):
            continue

        if (
            situacao_filtro
            and normalizar_filtro(
                situacao_registro
            ) != situacao_filtro
        ):
            continue

        registros.append(
            {
                "supervisor":
                    supervisor_registro,

                "subsupervisor":
                    subsupervisor_registro,

                "nome":
                    limpar_texto(
                        registro.get(
                            "nome",
                            ""
                        )
                    ),

                "comunidade":
                    limpar_texto(
                        registro.get(
                            "comunidade",
                            ""
                        )
                    ),

                "telefone":
                    limpar_texto(
                        registro.get(
                            "telefone",
                            ""
                        )
                    ),

                "situacao":
                    situacao_registro
            }
        )

    registros.sort(
        key=lambda item: (
            normalizar_filtro(
                item["supervisor"]
            ),

            normalizar_filtro(
                item["subsupervisor"]
            ),

            normalizar_filtro(
                item["nome"]
            )
        )
    )

    return registros


# ============================================================
# AGRUPAR SUPERVISOR / SUBSUPERVISOR
# ============================================================

def agrupar_relatorio_nome(registros):
    """
    Agrupa o relatório por:

    Supervisor
        ↓
    Subsupervisor
        ↓
    Pessoas
    """

    grupos = []

    grupo_atual = None
    chave_atual = None

    for registro in registros:

        supervisor = limpar_texto(
            registro.get(
                "supervisor",
                ""
            )
        )

        subsupervisor = limpar_texto(
            registro.get(
                "subsupervisor",
                ""
            )
        )

        chave = (
            normalizar_filtro(
                supervisor
            ),
            normalizar_filtro(
                subsupervisor
            )
        )

        if chave != chave_atual:

            grupo_atual = {
                "supervisor":
                    supervisor
                    or "SEM SUPERVISOR",

                "subsupervisor":
                    subsupervisor
                    or "SEM SUBSUPERVISOR",

                "registros": []
            }

            grupos.append(
                grupo_atual
            )

            chave_atual = chave

        grupo_atual[
            "registros"
        ].append(
            registro
        )

    return grupos


# ============================================================
# GERAR ESTRUTURA DO RELATÓRIO POR NOME
# ============================================================

def gerar_relatorio_nome(
    dados_base,
    supervisor="",
    subsupervisor="",
    situacao=""
):
    """
    Executa todo o processamento necessário
    para o Relatório por Nome.

    Retorno pronto para o app.py.
    """

    registros = filtrar_relatorio_nome(
        dados_base=dados_base,
        supervisor=supervisor,
        subsupervisor=subsupervisor,
        situacao=situacao
    )

    grupos = agrupar_relatorio_nome(
        registros
    )

    return {
        "tipo":
            "nome",

        "titulo":
            "Relatório por Nome",

        "total":
            len(registros),

        "filtros": {
            "supervisor":
                limpar_texto(
                    supervisor
                ),

            "subsupervisor":
                limpar_texto(
                    subsupervisor
                ),

            "situacao":
                limpar_texto(
                    situacao
                )
        },

        "registros":
            registros,

        "grupos":
            grupos
    }


# ============================================================
# PDF - ESTILOS
# ============================================================

def _estilos_pdf():

    estilos_base = getSampleStyleSheet()

    titulo = ParagraphStyle(
        "TituloRelatorio",
        parent=estilos_base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        alignment=TA_CENTER,
        spaceAfter=4
    )

    subtitulo = ParagraphStyle(
        "SubtituloRelatorio",
        parent=estilos_base["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor(
            "#666666"
        )
    )

    grupo = ParagraphStyle(
        "GrupoRelatorio",
        parent=estilos_base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        alignment=TA_LEFT,
        textColor=colors.HexColor(
            "#1F2937"
        )
    )

    texto = ParagraphStyle(
        "TextoTabela",
        parent=estilos_base["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
        alignment=TA_LEFT
    )

    texto_centro = ParagraphStyle(
        "TextoTabelaCentro",
        parent=texto,
        alignment=TA_CENTER
    )

    return {
        "titulo": titulo,
        "subtitulo": subtitulo,
        "grupo": grupo,
        "texto": texto,
        "texto_centro": texto_centro
    }


# ============================================================
# PDF - CABEÇALHO E RODAPÉ
# ============================================================

def _cabecalho_rodape_pdf(
    canvas,
    doc
):
    """
    Informações fixas da página.

    O Supervisor/Subsupervisor é tratado
    dentro de cada tabela de grupo para poder
    ser repetido quando a tabela quebra de página.
    """

    canvas.saveState()

    largura, altura = A4

    canvas.setFont(
        "Helvetica",
        7
    )

    canvas.setFillColor(
        colors.HexColor(
            "#777777"
        )
    )

    data_geracao = datetime.now().strftime(
        "%d/%m/%Y %H:%M"
    )

    canvas.drawString(
        1.3 * cm,
        0.7 * cm,
        f"Gerado em {data_geracao}"
    )

    canvas.drawRightString(
        largura - 1.3 * cm,
        0.7 * cm,
        f"Página {doc.page}"
    )

    canvas.restoreState()


# ============================================================
# PDF - TABELA DE UM GRUPO
# ============================================================

def _montar_tabela_grupo(
    grupo,
    estilos
):
    """
    Cria uma tabela para Supervisor/Subsupervisor.

    As duas primeiras linhas são:
    1. identificação Supervisor/Subsupervisor
    2. cabeçalho das colunas

    repeatRows=2 faz essas duas linhas serem
    repetidas automaticamente quando a tabela
    continuar na página seguinte.
    """

    supervisor = limpar_texto(
        grupo.get(
            "supervisor",
            ""
        )
    ) or "SEM SUPERVISOR"

    subsupervisor = limpar_texto(
        grupo.get(
            "subsupervisor",
            ""
        )
    ) or "SEM SUBSUPERVISOR"

    registros = grupo.get(
        "registros",
        []
    )

    identificacao = Paragraph(
        (
            f"<b>Supervisor:</b> {supervisor}"
            f"&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<b>Subsupervisor:</b> {subsupervisor}"
            f"&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<b>Total:</b> {len(registros)}"
        ),
        estilos["grupo"]
    )

    dados_tabela = [
        [
            identificacao,
            "",
            "",
            ""
        ],
        [
            Paragraph(
                "<b>Nº</b>",
                estilos["texto_centro"]
            ),
            Paragraph(
                "<b>NOME</b>",
                estilos["texto"]
            ),
            Paragraph(
                "<b>COMUNIDADE</b>",
                estilos["texto"]
            ),
            Paragraph(
                "<b>TELEFONE</b>",
                estilos["texto"]
            )
        ]
    ]

    for numero, registro in enumerate(
        registros,
        start=1
    ):

        nome = limpar_texto(
            registro.get(
                "nome",
                ""
            )
        )

        comunidade = limpar_texto(
            registro.get(
                "comunidade",
                ""
            )
        )

        telefone = limpar_texto(
            registro.get(
                "telefone",
                ""
            )
        )

        dados_tabela.append(
            [
                Paragraph(
                    str(numero),
                    estilos["texto_centro"]
                ),
                Paragraph(
                    nome or "—",
                    estilos["texto"]
                ),
                Paragraph(
                    comunidade or "—",
                    estilos["texto"]
                ),
                Paragraph(
                    telefone or "—",
                    estilos["texto"]
                )
            ]
        )

    tabela = Table(
        dados_tabela,
        colWidths=[
            1.0 * cm,
            8.2 * cm,
            5.0 * cm,
            3.5 * cm
        ],
        repeatRows=2,
        hAlign="CENTER"
    )

    tabela.setStyle(
        TableStyle(
            [
                # Linha Supervisor/Subsupervisor
                (
                    "SPAN",
                    (0, 0),
                    (-1, 0)
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#EAF2F8"
                    )
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor(
                        "#C9D2DC"
                    )
                ),
                (
                    "LINEBELOW",
                    (0, 0),
                    (-1, 0),
                    0.7,
                    colors.HexColor(
                        "#8EA9C1"
                    )
                ),

                # Cabeçalho
                (
                    "BACKGROUND",
                    (0, 1),
                    (-1, 1),
                    colors.HexColor(
                        "#F2F4F7"
                    )
                ),
                (
                    "TEXTCOLOR",
                    (0, 1),
                    (-1, 1),
                    colors.HexColor(
                        "#374151"
                    )
                ),
                (
                    "LINEBELOW",
                    (0, 1),
                    (-1, 1),
                    0.5,
                    colors.HexColor(
                        "#B8C2CC"
                    )
                ),

                # Corpo
                (
                    "GRID",
                    (0, 2),
                    (-1, -1),
                    0.25,
                    colors.HexColor(
                        "#D9DEE5"
                    )
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4
                )
            ]
        )
    )

    return tabela


# ============================================================
# GERAR PDF DO RELATÓRIO POR NOME
# ============================================================

def gerar_pdf_relatorio_nome(
    resultado_relatorio
):
    """
    Gera o PDF do Relatório por Nome.

    Retorna os bytes do PDF para uso direto
    em st.download_button().
    """

    buffer = BytesIO()

    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.3 * cm,
        leftMargin=1.3 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title="Relatório por Nome"
    )

    estilos = _estilos_pdf()

    elementos = []

    elementos.append(
        Paragraph(
            "RELATÓRIO POR NOME",
            estilos["titulo"]
        )
    )

    filtros = resultado_relatorio.get(
        "filtros",
        {}
    )

    situacao = limpar_texto(
        filtros.get(
            "situacao",
            ""
        )
    )

    total = resultado_relatorio.get(
        "total",
        0
    )

    resumo = (
        f"Total de registros: {total}"
    )

    if situacao:
        resumo += (
            f" &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"Situação: {situacao}"
        )

    elementos.append(
        Paragraph(
            resumo,
            estilos["subtitulo"]
        )
    )

    elementos.append(
        Spacer(
            1,
            0.35 * cm
        )
    )

    grupos = resultado_relatorio.get(
        "grupos",
        []
    )

    if not grupos:

        elementos.append(
            Paragraph(
                "Nenhum registro encontrado.",
                estilos["texto"]
            )
        )

    else:

        for indice, grupo in enumerate(
            grupos
        ):

            tabela = _montar_tabela_grupo(
                grupo,
                estilos
            )

            elementos.append(
                tabela
            )

            if indice < len(grupos) - 1:
                elementos.append(
                    Spacer(
                        1,
                        0.35 * cm
                    )
                )

    documento.build(
        elementos,
        onFirstPage=_cabecalho_rodape_pdf,
        onLaterPages=_cabecalho_rodape_pdf
    )

    pdf = buffer.getvalue()

    buffer.close()

    return pdf

# ============================================================
# GERAR HTML IMPRIMÍVEL DO RELATÓRIO POR NOME
# ============================================================

def gerar_html_relatorio_nome(resultado_relatorio):
    """
    Gera uma janela de impressão do Relatório por Nome.

    O HTML é aberto pelo app em um popup do navegador.
    Supervisor/Subsupervisor e cabeçalho da tabela
    são repetidos nas páginas impressas.
    """

    def escapar(valor):
        return html.escape(
            limpar_texto(valor)
        )

    filtros = resultado_relatorio.get(
        "filtros",
        {}
    )

    situacao = limpar_texto(
        filtros.get(
            "situacao",
            ""
        )
    )

    total = resultado_relatorio.get(
        "total",
        0
    )

    grupos = resultado_relatorio.get(
        "grupos",
        []
    )

    partes = []

    for grupo in grupos:

        supervisor = escapar(
            grupo.get(
                "supervisor",
                ""
            ) or "SEM SUPERVISOR"
        )

        subsupervisor = escapar(
            grupo.get(
                "subsupervisor",
                ""
            ) or "SEM SUBSUPERVISOR"
        )

        registros = grupo.get(
            "registros",
            []
        )

        linhas = []

        for numero, registro in enumerate(
            registros,
            start=1
        ):
            linhas.append(
                f"""
                <tr>
                    <td class="numero">{numero}</td>
                    <td>{escapar(registro.get("nome", "")) or "—"}</td>
                    <td>{escapar(registro.get("comunidade", "")) or "—"}</td>
                    <td>{escapar(registro.get("telefone", "")) or "—"}</td>
                </tr>
                """
            )

        partes.append(
            f"""
            <section class="grupo">
                <table>
                    <thead>
                        <tr class="identificacao">
                            <th colspan="4">
                                Supervisor: {supervisor}
                                &nbsp;&nbsp;&nbsp;
                                Subsupervisor: {subsupervisor}
                                &nbsp;&nbsp;&nbsp;
                                Total: {len(registros)}
                            </th>
                        </tr>
                        <tr class="cabecalho">
                            <th class="numero">Nº</th>
                            <th>Nome</th>
                            <th>Comunidade</th>
                            <th>Telefone</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(linhas)}
                    </tbody>
                </table>
            </section>
            """
        )

    situacao_html = (
        f" &nbsp;|&nbsp; Situação: {escapar(situacao)}"
        if situacao
        else ""
    )

    conteudo = "".join(partes)

    if not conteudo:
        conteudo = "<p>Nenhum registro encontrado.</p>"

    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Relatório por Nome</title>

        <style>
            @page {{
                size: A4;
                margin: 12mm;
            }}

            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                font-family: Arial, sans-serif;
                color: #1f2937;
                background: white;
                font-size: 11px;
            }}

            .acoes {{
                position: sticky;
                top: 0;
                display: flex;
                justify-content: flex-end;
                gap: 8px;
                padding: 10px 0;
                background: white;
                border-bottom: 1px solid #ddd;
                margin-bottom: 12px;
            }}

            button {{
                border: 0;
                border-radius: 6px;
                padding: 8px 16px;
                cursor: pointer;
                font-weight: 600;
            }}

            .imprimir {{
                background: #0b5fc6;
                color: white;
            }}

            .fechar {{
                background: #e5e7eb;
                color: #111827;
            }}

            h1 {{
                text-align: center;
                font-size: 17px;
                margin: 0 0 4px 0;
            }}

            .resumo {{
                text-align: center;
                color: #666;
                margin-bottom: 12px;
            }}

            .grupo {{
                margin-bottom: 12px;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                table-layout: fixed;
            }}

            thead {{
                display: table-header-group;
            }}

            tr {{
                break-inside: avoid;
                page-break-inside: avoid;
            }}

            th,
            td {{
                border: 1px solid #d7dce2;
                padding: 5px 6px;
                text-align: left;
                vertical-align: middle;
            }}

            .identificacao th {{
                background: #eaf2f8;
                font-weight: 700;
            }}

            .cabecalho th {{
                background: #f2f4f7;
            }}

            .numero {{
                width: 7%;
                text-align: center;
            }}

            th:nth-child(2),
            td:nth-child(2) {{
                width: 45%;
            }}

            th:nth-child(3),
            td:nth-child(3) {{
                width: 28%;
            }}

            th:nth-child(4),
            td:nth-child(4) {{
                width: 20%;
            }}

            @media print {{
                .acoes {{
                    display: none !important;
                }}

                body {{
                    font-size: 9px;
                }}

                .grupo {{
                    margin-bottom: 8px;
                }}
            }}
        </style>
    </head>

    <body>
        <div class="acoes">
            <button
                class="imprimir"
                onclick="window.print()"
            >
                🖨️ Imprimir
            </button>

            <button
                class="fechar"
                onclick="window.close()"
            >
                Fechar
            </button>
        </div>

        <h1>RELATÓRIO POR NOME</h1>

        <div class="resumo">
            Total de registros: {total}{situacao_html}
        </div>

        {conteudo}

        <script>
            /*
             * O app injeta esta página em um componente.
             * Abrimos o conteúdo em uma janela separada para
             * que o navegador possa imprimir somente o relatório.
             */
            window.addEventListener("load", function() {{
                const popup = window.open(
                    "",
                    "relatorio_impressao",
                    "width=1000,height=760,scrollbars=yes,resizable=yes"
                );

                if (popup) {{
                    popup.document.open();
                    popup.document.write(
                        document.documentElement.outerHTML
                    );
                    popup.document.close();
                }}
            }});
        </script>
    </body>
    </html>
    """

# ============================================================
# RELATÓRIO POR ZONA
# ============================================================

def _chave_num_relatorio(valor):
    texto = limpar_texto(valor)
    numeros = "".join(c for c in texto if c.isdigit())
    return (int(numeros) if numeros else 10**12, texto.upper())


def obter_filtros_zona(dados_base):
    supervisores, subsupervisores = set(), set()
    situacoes, zonas, secoes = set(), set(), set()

    for registro in dados_base or []:
        campos = {
            "supervisor": limpar_texto(registro.get("supervisor", "")),
            "subsupervisor": limpar_texto(registro.get("subsupervisor", "")),
            "situacao": limpar_texto(registro.get("situacao", "")),
            "zona": limpar_texto(registro.get("zona", "")),
            "secao": limpar_texto(registro.get("secao", ""))
        }
        if campos["supervisor"]: supervisores.add(campos["supervisor"])
        if campos["subsupervisor"]: subsupervisores.add(campos["subsupervisor"])
        if campos["situacao"]: situacoes.add(campos["situacao"])
        if campos["zona"]: zonas.add(campos["zona"])
        if campos["secao"]: secoes.add(campos["secao"])

    return {
        "supervisores": sorted(supervisores, key=str.upper),
        "subsupervisores": sorted(subsupervisores, key=str.upper),
        "situacoes": sorted(situacoes, key=str.upper),
        "zonas": sorted(zonas, key=_chave_num_relatorio),
        "secoes": sorted(secoes, key=_chave_num_relatorio)
    }


def obter_secoes_por_zona(dados_base, zona=""):
    zona_filtro = normalizar_filtro(zona)
    secoes = set()

    for registro in dados_base or []:
        zona_registro = limpar_texto(registro.get("zona", ""))
        if zona_filtro and normalizar_filtro(zona_registro) != zona_filtro:
            continue
        secao = limpar_texto(registro.get("secao", ""))
        if secao:
            secoes.add(secao)

    return sorted(secoes, key=_chave_num_relatorio)


def filtrar_relatorio_zona(
    dados_base,
    supervisor="",
    subsupervisor="",
    zona="",
    secao="",
    situacao=""
):
    filtros = {
        "supervisor": normalizar_filtro(supervisor),
        "subsupervisor": normalizar_filtro(subsupervisor),
        "zona": normalizar_filtro(zona),
        "secao": normalizar_filtro(secao),
        "situacao": normalizar_filtro(situacao)
    }

    registros = []

    for registro in dados_base or []:
        atual = {
            "supervisor": limpar_texto(registro.get("supervisor", "")),
            "subsupervisor": limpar_texto(registro.get("subsupervisor", "")),
            "zona": limpar_texto(registro.get("zona", "")),
            "secao": limpar_texto(registro.get("secao", "")),
            "situacao": limpar_texto(registro.get("situacao", ""))
        }

        if any(
            filtros[chave] and normalizar_filtro(atual[chave]) != filtros[chave]
            for chave in filtros
        ):
            continue

        registros.append({
            **atual,
            "nome": limpar_texto(registro.get("nome", "")),
            "comunidade": limpar_texto(registro.get("comunidade", "")),
            "telefone": limpar_texto(registro.get("telefone", ""))
        })

    registros.sort(
        key=lambda item: (
            _chave_num_relatorio(item["zona"]),
            _chave_num_relatorio(item["secao"]),
            normalizar_filtro(item["nome"])
        )
    )
    return registros


def resumir_relatorio_zona(registros):
    mapa = {}

    for registro in registros:
        zona = limpar_texto(registro.get("zona", "")) or "SEM ZONA"
        secao = limpar_texto(registro.get("secao", "")) or "SEM SEÇÃO"
        mapa.setdefault(zona, {})
        mapa[zona][secao] = mapa[zona].get(secao, 0) + 1

    resumo = []
    for zona in sorted(mapa, key=_chave_num_relatorio):
        secoes = [
            {"secao": secao, "total": mapa[zona][secao]}
            for secao in sorted(mapa[zona], key=_chave_num_relatorio)
        ]
        resumo.append({
            "zona": zona,
            "secoes": secoes,
            "total": sum(item["total"] for item in secoes)
        })

    return resumo


def gerar_relatorio_zona(
    dados_base,
    supervisor="",
    subsupervisor="",
    zona="",
    secao="",
    situacao=""
):
    registros = filtrar_relatorio_zona(
        dados_base, supervisor, subsupervisor, zona, secao, situacao
    )

    return {
        "tipo": "zona",
        "titulo": "Relatório por Zona",
        "total": len(registros),
        "total_zonas": len({r["zona"] for r in registros if r["zona"]}),
        "total_secoes": len({
            (r["zona"], r["secao"])
            for r in registros if r["secao"]
        }),
        "filtros": {
            "supervisor": limpar_texto(supervisor),
            "subsupervisor": limpar_texto(subsupervisor),
            "zona": limpar_texto(zona),
            "secao": limpar_texto(secao),
            "situacao": limpar_texto(situacao)
        },
        "registros": registros,
        "resumo": resumir_relatorio_zona(registros)
    }


def gerar_pdf_relatorio_zona(resultado_relatorio):
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.0 * cm,
        leftMargin=1.0 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title="Relatório por Zona"
    )

    estilos = _estilos_pdf()
    elementos = [
        Paragraph("RELATÓRIO POR ZONA", estilos["titulo"])
    ]

    total = resultado_relatorio.get("total", 0)
    total_zonas = resultado_relatorio.get("total_zonas", 0)
    total_secoes = resultado_relatorio.get("total_secoes", 0)
    filtros = resultado_relatorio.get("filtros", {})

    linha_filtros = []
    for rotulo, chave in (
        ("Supervisor", "supervisor"),
        ("Subsupervisor", "subsupervisor"),
        ("Zona", "zona"),
        ("Seção", "secao"),
        ("Situação", "situacao")
    ):
        valor = limpar_texto(filtros.get(chave, ""))
        if valor:
            linha_filtros.append(f"{rotulo}: {valor}")

    topo = f"Total: {total} &nbsp;|&nbsp; Zonas: {total_zonas} &nbsp;|&nbsp; Seções: {total_secoes}"
    if linha_filtros:
        topo += "<br/>" + " &nbsp;|&nbsp; ".join(linha_filtros)

    elementos += [
        Paragraph(topo, estilos["subtitulo"]),
        Spacer(1, 0.35 * cm)
    ]

    registros = resultado_relatorio.get("registros", [])

    if registros:
        dados = [[
            Paragraph("<b>Nº</b>", estilos["texto_centro"]),
            Paragraph("<b>ZONA</b>", estilos["texto_centro"]),
            Paragraph("<b>SEÇÃO</b>", estilos["texto_centro"]),
            Paragraph("<b>NOME</b>", estilos["texto"]),
            Paragraph("<b>COMUNIDADE</b>", estilos["texto"]),
            Paragraph("<b>TELEFONE</b>", estilos["texto"])
        ]]

        for numero, r in enumerate(registros, 1):
            dados.append([
                Paragraph(str(numero), estilos["texto_centro"]),
                Paragraph(r["zona"] or "—", estilos["texto_centro"]),
                Paragraph(r["secao"] or "—", estilos["texto_centro"]),
                Paragraph(r["nome"] or "—", estilos["texto"]),
                Paragraph(r["comunidade"] or "—", estilos["texto"]),
                Paragraph(r["telefone"] or "—", estilos["texto"])
            ])

        tabela = Table(
            dados,
            colWidths=[0.8*cm, 1.3*cm, 1.5*cm, 6.4*cm, 4.3*cm, 3.7*cm],
            repeatRows=1
        )
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EAF2F8")),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#D9DEE5")),
            ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#C9D2DC")),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
            ("RIGHTPADDING", (0,0), (-1,-1), 4),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3)
        ]))
        elementos += [tabela, Spacer(1, 0.55*cm)]

        elementos.append(
            Paragraph("RESUMO POR ZONA E SEÇÃO", estilos["grupo"])
        )
        elementos.append(Spacer(1, 0.18*cm))

        resumo_dados = [[
            Paragraph("<b>ZONA</b>", estilos["texto"]),
            Paragraph("<b>SEÇÃO</b>", estilos["texto"]),
            Paragraph("<b>QUANTIDADE</b>", estilos["texto_centro"])
        ]]

        linhas_total_zona = []
        for grupo in resultado_relatorio.get("resumo", []):
            zona = grupo["zona"]
            for item in grupo["secoes"]:
                resumo_dados.append([
                    Paragraph(zona, estilos["texto"]),
                    Paragraph(item["secao"], estilos["texto"]),
                    Paragraph(str(item["total"]), estilos["texto_centro"])
                ])
            linhas_total_zona.append(len(resumo_dados))
            resumo_dados.append([
                Paragraph(f"<b>TOTAL ZONA {zona}</b>", estilos["texto"]),
                "",
                Paragraph(f"<b>{grupo['total']}</b>", estilos["texto_centro"])
            ])

        resumo_dados.append([
            Paragraph("<b>TOTAL GERAL</b>", estilos["texto"]),
            "",
            Paragraph(f"<b>{total}</b>", estilos["texto_centro"])
        ])

        tabela_resumo = Table(
            resumo_dados,
            colWidths=[5.5*cm, 5.5*cm, 4.0*cm],
            repeatRows=1
        )

        estilo_resumo = [
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F7")),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#D9DEE5")),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("SPAN", (0,-1), (1,-1))
        ]

        for linha in linhas_total_zona:
            estilo_resumo += [
                ("SPAN", (0,linha), (1,linha)),
                ("BACKGROUND", (0,linha), (-1,linha), colors.HexColor("#EAF2F8"))
            ]

        tabela_resumo.setStyle(TableStyle(estilo_resumo))
        elementos.append(tabela_resumo)

    else:
        elementos.append(
            Paragraph("Nenhum registro encontrado.", estilos["texto"])
        )

    documento.build(
        elementos,
        onFirstPage=_cabecalho_rodape_pdf,
        onLaterPages=_cabecalho_rodape_pdf
    )

    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# ============================================================
# RELATÓRIO POR DOMICÍLIO
# ============================================================

def obter_filtros_domicilio(dados_base):
    supervisores, subsupervisores, domicilios, situacoes = set(), set(), set(), set()
    for r in dados_base or []:
        supervisor = limpar_texto(r.get("supervisor", ""))
        subsupervisor = limpar_texto(r.get("subsupervisor", ""))
        domicilio = limpar_texto(r.get("domicilio", ""))
        situacao = limpar_texto(r.get("situacao", ""))
        if supervisor: supervisores.add(supervisor)
        if subsupervisor: subsupervisores.add(subsupervisor)
        if domicilio: domicilios.add(domicilio)
        if situacao: situacoes.add(situacao)
    return {
        "supervisores": sorted(supervisores, key=str.upper),
        "subsupervisores": sorted(subsupervisores, key=str.upper),
        "domicilios": sorted(domicilios, key=str.upper),
        "situacoes": sorted(situacoes, key=str.upper)
    }


def filtrar_relatorio_domicilio(dados_base, supervisor="", subsupervisor="", domicilio="", situacao=""):
    fs = normalizar_filtro(supervisor)
    fsub = normalizar_filtro(subsupervisor)
    fd = normalizar_filtro(domicilio)
    fsi = normalizar_filtro(situacao)
    registros = []

    for r in dados_base or []:
        sup = limpar_texto(r.get("supervisor", ""))
        sub = limpar_texto(r.get("subsupervisor", ""))
        dom = limpar_texto(r.get("domicilio", ""))
        sit = limpar_texto(r.get("situacao", ""))

        if fs and normalizar_filtro(sup) != fs: continue
        if fsub and normalizar_filtro(sub) != fsub: continue
        if fd and normalizar_filtro(dom) != fd: continue
        if fsi and normalizar_filtro(sit) != fsi: continue

        registros.append({
            "supervisor": sup,
            "subsupervisor": sub,
            "domicilio": dom,
            "nome": limpar_texto(r.get("nome", "")),
            "comunidade": limpar_texto(r.get("comunidade", "")),
            "telefone": limpar_texto(r.get("telefone", "")),
            "situacao": sit
        })

    registros.sort(key=lambda x: (
        normalizar_filtro(x["domicilio"]),
        normalizar_filtro(x["nome"])
    ))
    return registros


def resumir_relatorio_domicilio(registros):
    totais = {}
    for r in registros:
        dom = limpar_texto(r.get("domicilio", "")) or "SEM DOMICÍLIO"
        totais[dom] = totais.get(dom, 0) + 1
    return [
        {"domicilio": dom, "total": totais[dom]}
        for dom in sorted(totais, key=str.upper)
    ]


def gerar_relatorio_domicilio(dados_base, supervisor="", subsupervisor="", domicilio="", situacao=""):
    registros = filtrar_relatorio_domicilio(
        dados_base, supervisor, subsupervisor, domicilio, situacao
    )
    return {
        "tipo": "domicilio",
        "titulo": "Relatório por Domicílio",
        "total": len(registros),
        "total_domicilios": len({
            normalizar_filtro(r["domicilio"])
            for r in registros if limpar_texto(r["domicilio"])
        }),
        "filtros": {
            "supervisor": limpar_texto(supervisor),
            "subsupervisor": limpar_texto(subsupervisor),
            "domicilio": limpar_texto(domicilio),
            "situacao": limpar_texto(situacao)
        },
        "registros": registros,
        "resumo": resumir_relatorio_domicilio(registros)
    }


def gerar_pdf_relatorio_domicilio(resultado_relatorio):
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.0*cm, leftMargin=1.0*cm,
        topMargin=1.2*cm, bottomMargin=1.2*cm,
        title="Relatório por Domicílio"
    )
    estilos = _estilos_pdf()
    elementos = [Paragraph("RELATÓRIO POR DOMICÍLIO", estilos["titulo"])]

    total = resultado_relatorio.get("total", 0)
    total_domicilios = resultado_relatorio.get("total_domicilios", 0)
    filtros = resultado_relatorio.get("filtros", {})
    partes = []
    for rotulo, chave in (
        ("Supervisor","supervisor"), ("Subsupervisor","subsupervisor"),
        ("Domicílio","domicilio"), ("Situação","situacao")
    ):
        valor = limpar_texto(filtros.get(chave, ""))
        if valor: partes.append(f"{rotulo}: {valor}")

    topo = f"Total: {total} &nbsp;|&nbsp; Domicílios: {total_domicilios}"
    if partes: topo += "<br/>" + " &nbsp;|&nbsp; ".join(partes)
    elementos += [Paragraph(topo, estilos["subtitulo"]), Spacer(1, 0.35*cm)]

    registros = resultado_relatorio.get("registros", [])
    if registros:
        dados = [[
            Paragraph("<b>Nº</b>", estilos["texto_centro"]),
            Paragraph("<b>DOMICÍLIO</b>", estilos["texto"]),
            Paragraph("<b>NOME</b>", estilos["texto"]),
            Paragraph("<b>COMUNIDADE</b>", estilos["texto"]),
            Paragraph("<b>TELEFONE</b>", estilos["texto"])
        ]]
        for n, r in enumerate(registros, 1):
            dados.append([
                Paragraph(str(n), estilos["texto_centro"]),
                Paragraph(r["domicilio"] or "—", estilos["texto"]),
                Paragraph(r["nome"] or "—", estilos["texto"]),
                Paragraph(r["comunidade"] or "—", estilos["texto"]),
                Paragraph(r["telefone"] or "—", estilos["texto"])
            ])

        tabela = Table(dados, colWidths=[0.8*cm,4.0*cm,6.2*cm,4.0*cm,3.0*cm], repeatRows=1)
        tabela.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#EAF2F8")),
            ("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#D9DEE5")),
            ("BOX",(0,0),(-1,-1),0.5,colors.HexColor("#C9D2DC")),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),
            ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)
        ]))
        elementos += [tabela, Spacer(1,0.55*cm),
                      Paragraph("RESUMO POR DOMICÍLIO", estilos["grupo"]),
                      Spacer(1,0.18*cm)]

        rd = [[Paragraph("<b>DOMICÍLIO</b>", estilos["texto"]),
               Paragraph("<b>QUANTIDADE</b>", estilos["texto_centro"])]]
        for item in resultado_relatorio.get("resumo", []):
            rd.append([
                Paragraph(item["domicilio"] or "—", estilos["texto"]),
                Paragraph(str(item["total"]), estilos["texto_centro"])
            ])
        rd.append([
            Paragraph("<b>TOTAL GERAL</b>", estilos["texto"]),
            Paragraph(f"<b>{total}</b>", estilos["texto_centro"])
        ])

        tr = Table(rd, colWidths=[11.0*cm,4.0*cm], repeatRows=1)
        tr.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#F2F4F7")),
            ("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#EAF2F8")),
            ("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#D9DEE5")),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE")
        ]))
        elementos.append(tr)
    else:
        elementos.append(Paragraph("Nenhum registro encontrado.", estilos["texto"]))

    documento.build(elementos, onFirstPage=_cabecalho_rodape_pdf, onLaterPages=_cabecalho_rodape_pdf)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# ============================================================
# RELATÓRIO DE CRUZAMENTOS
# ============================================================

def _normalizar_titulo_cruzamento(valor):
    titulo = "".join(
        c for c in limpar_texto(valor)
        if c.isdigit()
    )

    return titulo.lstrip("0")


def obter_filtros_cruzamentos(
    dados_base,
    bases_concorrentes=None
):
    filtros = obter_filtros_nome(
        dados_base
    )

    bases = []

    for nome_base in (
        bases_concorrentes or {}
    ).keys():
        nome = limpar_texto(
            nome_base
        ).upper()

        if nome:
            bases.append(
                nome
            )

    filtros["bases"] = sorted(
        set(bases),
        key=str.upper
    )

    return filtros


def filtrar_relatorio_cruzamentos(
    dados_base,
    supervisor="",
    subsupervisor="",
    situacao=""
):
    fs = normalizar_filtro(supervisor)
    fsub = normalizar_filtro(subsupervisor)
    fsi = normalizar_filtro(situacao)
    registros = []

    for r in dados_base or []:
        sup = limpar_texto(r.get("supervisor", ""))
        sub = limpar_texto(r.get("subsupervisor", ""))
        sit = limpar_texto(r.get("situacao", ""))

        if fs and normalizar_filtro(sup) != fs:
            continue
        if fsub and normalizar_filtro(sub) != fsub:
            continue
        if fsi and normalizar_filtro(sit) != fsi:
            continue

        registros.append({
            "supervisor": sup,
            "subsupervisor": sub,
            "nome": limpar_texto(r.get("nome", "")),
            "comunidade": limpar_texto(r.get("comunidade", "")),
            "telefone": limpar_texto(r.get("telefone", "")),
            "titulo": _normalizar_titulo_cruzamento(r.get("titulo", "")),
            "situacao": sit
        })

    registros.sort(key=lambda x: (
        normalizar_filtro(x["supervisor"]),
        normalizar_filtro(x["subsupervisor"]),
        normalizar_filtro(x["nome"])
    ))
    return registros


def gerar_relatorio_cruzamentos(
    dados_base,
    bases_concorrentes,
    supervisor="",
    subsupervisor="",
    situacao="",
    base_cruzada="",
    resultado_cruzamento=""
):
    registros = filtrar_relatorio_cruzamentos(
        dados_base,
        supervisor,
        subsupervisor,
        situacao
    )

    nomes_bases = sorted(
        [
            limpar_texto(nome).upper()
            for nome in (bases_concorrentes or {}).keys()
            if limpar_texto(nome)
        ],
        key=str.upper
    )

    # Monta um SET normalizado para cada base.
    # Assim cada pessoa é comparada contra TODAS as bases
    # e pode cruzar em AF + FL + TIM etc. ao mesmo tempo.
    titulos_por_base = {}

    for nome_original, valores in (bases_concorrentes or {}).items():
        nome_base = limpar_texto(nome_original).upper()

        if not nome_base:
            continue

        conjunto = set()

        if isinstance(valores, (list, tuple, set)):
            for valor in valores:
                titulo_base = _normalizar_titulo_cruzamento(valor)
                if titulo_base:
                    conjunto.add(titulo_base)

        titulos_por_base[nome_base] = conjunto

    for r in registros:
        titulo = _normalizar_titulo_cruzamento(
            r.get("titulo", "")
        )

        bases_encontradas = []

        if titulo:
            for base in nomes_bases:
                if titulo in titulos_por_base.get(base, set()):
                    bases_encontradas.append(base)

        cruzamentos = {
            base: base in bases_encontradas
            for base in nomes_bases
        }

        r["cruzamentos"] = cruzamentos
        r["bases_cruzadas"] = bases_encontradas
        r["cruzamentos_texto"] = " | ".join(bases_encontradas)
        r["cruzou_alguma"] = bool(bases_encontradas)

    base_filtro = normalizar_filtro(base_cruzada)
    resultado_filtro = normalizar_filtro(resultado_cruzamento)

    registros_filtrados = []

    for r in registros:
        if base_filtro:
            cruzou_base = bool(
                r.get("cruzamentos", {}).get(base_filtro)
            )

            if resultado_filtro == "CRUZOU" and not cruzou_base:
                continue

            if (
                resultado_filtro in ("NÃO CRUZOU", "NAO CRUZOU")
                and cruzou_base
            ):
                continue

        else:
            if (
                resultado_filtro == "CRUZOU"
                and not r["cruzou_alguma"]
            ):
                continue

            if (
                resultado_filtro in ("NÃO CRUZOU", "NAO CRUZOU")
                and r["cruzou_alguma"]
            ):
                continue

        registros_filtrados.append(r)

    resumo = {
        b: {
            "base": b,
            "cruzaram": 0,
            "nao_cruzaram": 0
        }
        for b in nomes_bases
    }

    total_com = 0
    total_sem = 0

    for r in registros_filtrados:
        if r["cruzou_alguma"]:
            total_com += 1
        else:
            total_sem += 1

        for b in nomes_bases:
            if r.get("cruzamentos", {}).get(b):
                resumo[b]["cruzaram"] += 1
            else:
                resumo[b]["nao_cruzaram"] += 1

    # No resumo aparecem apenas bases que tiveram cruzamento.
    resumo_bases = [
        resumo[b]
        for b in nomes_bases
        if resumo[b]["cruzaram"] > 0
    ]

    return {
        "tipo": "cruzamentos",
        "titulo": "Relatório de Cruzamentos",
        "total": len(registros_filtrados),
        "total_com_cruzamento": total_com,
        "total_sem_cruzamento": total_sem,
        "bases": nomes_bases,
        "resumo_bases": resumo_bases,
        "filtros": {
            "supervisor": limpar_texto(supervisor),
            "subsupervisor": limpar_texto(subsupervisor),
            "situacao": limpar_texto(situacao),
            "base_cruzada": limpar_texto(base_cruzada).upper(),
            "resultado_cruzamento": limpar_texto(resultado_cruzamento)
        },
        "registros": registros_filtrados,
        "grupos": agrupar_relatorio_nome(
            registros_filtrados
        )
    }

def gerar_pdf_relatorio_cruzamentos(resultado_relatorio):
    from reportlab.lib.pagesizes import landscape

    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=0.7*cm,
        leftMargin=0.7*cm,
        topMargin=1.0*cm,
        bottomMargin=1.1*cm,
        title="Relatório de Cruzamentos"
    )

    estilos = _estilos_pdf()

    # Estilo exclusivo do marcador no PDF.
    estilo_marcador_pdf = ParagraphStyle(
        "MarcadorCruzamentoPDF",
        parent=estilos["texto_centro"],
        fontName="Helvetica-Bold",
        fontSize=5,
        leading=5,
        alignment=TA_CENTER,
        spaceBefore=0,
        spaceAfter=0
    )

    elementos = [
        Paragraph("RELATÓRIO DE CRUZAMENTOS", estilos["titulo"])
    ]

    total = resultado_relatorio.get("total", 0)
    filtros = resultado_relatorio.get("filtros", {})
    partes = []

    for rotulo, chave in (
        ("Supervisor", "supervisor"),
        ("Subsupervisor", "subsupervisor"),
        ("Situação", "situacao"),
        ("Base", "base_cruzada"),
        ("Resultado", "resultado_cruzamento")
    ):
        valor = limpar_texto(filtros.get(chave, ""))
        if valor:
            partes.append(f"{rotulo}: {valor}")

    topo = f"Total de registros: {total}"
    if partes:
        topo += "<br/>" + " &nbsp;|&nbsp; ".join(partes)

    elementos += [
        Paragraph(topo, estilos["subtitulo"]),
        Spacer(1, 0.35*cm)
    ]

    grupos = resultado_relatorio.get("grupos", [])

    if grupos:
        for indice_grupo, grupo in enumerate(grupos):
            supervisor = limpar_texto(
                grupo.get("supervisor", "")
            ) or "SEM SUPERVISOR"

            subsupervisor = limpar_texto(
                grupo.get("subsupervisor", "")
            ) or "SEM SUBSUPERVISOR"

            registros = grupo.get("registros", [])

            total_colunas = 5

            identificacao = Paragraph(
                f"<b>Supervisor:</b> {supervisor}"
                f"&nbsp;&nbsp;&nbsp;&nbsp;"
                f"<b>Subsupervisor:</b> {subsupervisor}"
                f"&nbsp;&nbsp;&nbsp;&nbsp;"
                f"<b>Total:</b> {len(registros)}",
                estilos["grupo"]
            )

            cabecalho = [
                Paragraph("<b>Nº</b>", estilos["texto_centro"]),
                Paragraph("<b>NOME</b>", estilos["texto"]),
                Paragraph("<b>COMUNIDADE</b>", estilos["texto"]),
                Paragraph("<b>TELEFONE</b>", estilos["texto"]),
                Paragraph("<b>CRUZAMENTOS</b>", estilos["texto"])
            ]

            dados = [
                [identificacao] + [""] * (total_colunas - 1),
                cabecalho
            ]

            for numero, r in enumerate(registros, 1):
                cruzou = bool(
                    r.get(
                        "cruzou_alguma"
                    )
                )

                nome = (
                    r.get(
                        "nome",
                        ""
                    )
                    or "—"
                )

                comunidade = (
                    r.get(
                        "comunidade",
                        ""
                    )
                    or "—"
                )

                telefone = (
                    r.get(
                        "telefone",
                        ""
                    )
                    or "—"
                )

                cruzamentos_texto = (
                    r.get(
                        "cruzamentos_texto",
                        ""
                    )
                    or "—"
                )

                # Marcador e número ficam na MESMA célula.
                # A bolinha invisível nas linhas sem cruzamento
                # mantém todos os números exatamente alinhados.
                if cruzou:
                    numero_pdf = (
                        '<font size="7"><b>●</b></font>'
                        '&nbsp;&nbsp;'
                        + str(numero)
                    )
                else:
                    numero_pdf = (
                        '<font color="#FFFFFF" size="7"><b>●</b></font>'
                        '&nbsp;&nbsp;'
                        + str(numero)
                    )

                if cruzou:
                    nome_pdf = (
                        f"<b>{nome}</b>"
                    )

                    cruzamentos_pdf = (
                        f"<b>{cruzamentos_texto}</b>"
                    )
                else:
                    nome_pdf = nome
                    cruzamentos_pdf = "—"

                linha = [
                    Paragraph(
                        numero_pdf,
                        estilos["texto_centro"]
                    ),
                    Paragraph(
                        nome_pdf,
                        estilos["texto"]
                    ),
                    Paragraph(
                        comunidade,
                        estilos["texto"]
                    ),
                    Paragraph(
                        telefone,
                        estilos["texto"]
                    ),
                    Paragraph(
                        cruzamentos_pdf,
                        estilos["texto"]
                    )
                ]

                dados.append(
                    linha
                )

            colunas = [
                1.55*cm,   # nº + marcador
                7.2*cm,    # nome
                4.5*cm,    # comunidade
                3.2*cm,    # telefone
                9.5*cm     # cruzamentos
            ]

            tabela = Table(
                dados,
                colWidths=colunas,
                repeatRows=2,
                hAlign="CENTER"
            )

            tabela.setStyle(TableStyle([
                ("SPAN", (0,0), (-1,0)),
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EAF2F8")),
                ("BACKGROUND", (0,1), (-1,1), colors.HexColor("#F2F4F7")),
                ("GRID", (0,1), (-1,-1), 0.25, colors.HexColor("#D9DEE5")),
                ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#C9D2DC")),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("LEFTPADDING", (0,0), (-1,-1), 3),
                ("RIGHTPADDING", (0,0), (-1,-1), 3),
                ("TOPPADDING", (0,0), (-1,-1), 3),
                ("BOTTOMPADDING", (0,0), (-1,-1), 3),
                ("ALIGN", (0,1), (0,-1), "CENTER")
            ]))

            elementos.append(tabela)

            if indice_grupo < len(grupos) - 1:
                elementos.append(Spacer(1, 0.35*cm))

        elementos += [
            Spacer(1, 0.55*cm),
            Paragraph("RESUMO DOS CRUZAMENTOS", estilos["grupo"]),
            Spacer(1, 0.18*cm)
        ]

        rd = [[
            Paragraph("<b>BASE</b>", estilos["texto"]),
            Paragraph("<b>CRUZARAM</b>", estilos["texto_centro"])
        ]]

        for item in resultado_relatorio.get("resumo_bases", []):
            rd.append([
                Paragraph(item["base"], estilos["texto"]),
                Paragraph(str(item["cruzaram"]), estilos["texto_centro"])
            ])

        tr = Table(
            rd,
            colWidths=[9.0*cm, 4.0*cm],
            repeatRows=1
        )

        tr.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F2F4F7")),
            ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#D9DEE5")),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE")
        ]))

        elementos.append(tr)
        elementos.append(Spacer(1, 0.25*cm))

        elementos.append(
            Paragraph(
                f"<b>Total exibido:</b> {total}"
                f"&nbsp;&nbsp;|&nbsp;&nbsp;"
                f"<b>Com cruzamento:</b> "
                f"{resultado_relatorio.get('total_com_cruzamento', 0)}"
                f"&nbsp;&nbsp;|&nbsp;&nbsp;"
                f"<b>Sem cruzamento:</b> "
                f"{resultado_relatorio.get('total_sem_cruzamento', 0)}",
                estilos["texto"]
            )
        )

    else:
        elementos.append(
            Paragraph("Nenhum registro encontrado.", estilos["texto"])
        )

    documento.build(
        elementos,
        onFirstPage=_cabecalho_rodape_pdf,
        onLaterPages=_cabecalho_rodape_pdf
    )

    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# ============================================================
# RELATÓRIO DE PAGAMENTOS DAS LIDERANÇAS
# ============================================================

def _valor_monetario_pagamentos(valor):
    """Converte valores exibidos pelo Google Sheets para float."""
    texto = limpar_texto(valor)

    if not texto:
        return 0.0

    texto = (
        texto.replace("R$", "")
        .replace(" ", "")
        .replace(".", "")
        .replace(",", ".")
    )

    try:
        return float(texto)
    except (TypeError, ValueError):
        return 0.0


def _inteiro_pagamentos(valor):
    texto = limpar_texto(valor)

    if not texto:
        return 0

    try:
        return int(float(texto.replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def _chave_pagamentos(registro, nome):
    """
    Localiza um campo independentemente de maiúsculas/minúsculas.
    Os cabeçalhos vindos do Apps Script são mantidos como estão na planilha.
    """
    alvo = limpar_texto(nome).upper()

    for chave, valor in (registro or {}).items():
        if limpar_texto(chave).upper() == alvo:
            return valor

    return ""


def _eh_coluna_data_pagamentos(cabecalho):
    texto = limpar_texto(cabecalho)

    for formato in ("%d/%m/%Y", "%d/%m/%y", "%d/%m"):
        try:
            datetime.strptime(texto, formato)
            return True
        except ValueError:
            pass

    return False


def _data_pagamentos(cabecalho):
    texto = limpar_texto(cabecalho)

    for formato in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            pass

    # Cabeçalhos antigos como 30/09 recebem o ano corrente apenas
    # para ordenação/exibição do relatório.
    try:
        return datetime.strptime(
            f"{texto}/{datetime.now().year}",
            "%d/%m/%Y"
        )
    except ValueError:
        return None


def _formatar_moeda_pagamentos(valor):
    numero = float(valor or 0)
    return (
        f"R$ {numero:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def obter_filtros_pagamentos(dados_pagamentos):
    supervisores = set()
    subsupervisores = set()
    comunidades = set()

    for registro in dados_pagamentos or []:
        supervisor = limpar_texto(
            _chave_pagamentos(registro, "SUPERVISOR")
        )
        subsupervisor = limpar_texto(
            _chave_pagamentos(registro, "SUBSUPERVISOR")
        )
        comunidade = limpar_texto(
            _chave_pagamentos(registro, "COMUNIDADE")
        )

        if supervisor:
            supervisores.add(supervisor)

        if subsupervisor:
            subsupervisores.add(subsupervisor)

        if comunidade:
            comunidades.add(comunidade)

    return {
        "supervisores": sorted(supervisores, key=str.upper),
        "subsupervisores": sorted(subsupervisores, key=str.upper),
        "comunidades": sorted(comunidades, key=str.upper),
    }


def gerar_relatorio_pagamentos(
    dados_pagamentos,
    supervisor="",
    subsupervisor="",
    comunidade=""
):
    fs = normalizar_filtro(supervisor)
    fsub = normalizar_filtro(subsupervisor)
    fc = normalizar_filtro(comunidade)

    registros = []
    colunas_data = set()

    for original in dados_pagamentos or []:
        sup = limpar_texto(
            _chave_pagamentos(original, "SUPERVISOR")
        )
        sub = limpar_texto(
            _chave_pagamentos(original, "SUBSUPERVISOR")
        )
        com = limpar_texto(
            _chave_pagamentos(original, "COMUNIDADE")
        )

        if fs and normalizar_filtro(sup) != fs:
            continue

        if fsub and normalizar_filtro(sub) != fsub:
            continue

        if fc and normalizar_filtro(com) != fc:
            continue

        qtde = _inteiro_pagamentos(
            _chave_pagamentos(original, "QTDE")
        )
        total = _valor_monetario_pagamentos(
            _chave_pagamentos(original, "TOTAL")
        )
        resta = _valor_monetario_pagamentos(
            _chave_pagamentos(original, "RESTA PAGAR")
        )

        # Para este controle, PAGO é o que já saiu do saldo a pagar.
        # Assim: PAGO = TOTAL - RESTA PAGAR.
        pago = max(
            0.0,
            total - resta
        )

        vencimentos = []

        for cabecalho, valor in (original or {}).items():
            if not _eh_coluna_data_pagamentos(cabecalho):
                continue

            valor_vencimento = _valor_monetario_pagamentos(valor)

            if valor_vencimento == 0:
                continue

            data_obj = _data_pagamentos(cabecalho)
            data_texto = limpar_texto(cabecalho)

            colunas_data.add(data_texto)

            vencimentos.append({
                "data": data_texto,
                "data_obj": data_obj,
                "valor": valor_vencimento,
            })

        registros.append({
            "supervisor": sup,
            "subsupervisor": sub,
            "comunidade": com,
            "qtde": qtde,
            "total": total,
            "pago": pago,
            "resta_pagar": resta,
            "vencimentos": vencimentos,
        })

    registros.sort(
        key=lambda r: (
            normalizar_filtro(r.get("supervisor", "")),
            normalizar_filtro(r.get("subsupervisor", "")),
            normalizar_filtro(r.get("comunidade", "")),
        )
    )

    total_previsto = sum(
        r["total"] for r in registros
    )
    total_pago = sum(
        r["pago"] for r in registros
    )
    total_resta = sum(
        r["resta_pagar"] for r in registros
    )
    total_pessoas = sum(
        r["qtde"] for r in registros
    )

    resumo_vencimentos = []

    for cabecalho in sorted(
        colunas_data,
        key=lambda d: _data_pagamentos(d) or datetime.max
    ):
        itens = []
        total_vencimento = 0.0
        pessoas = 0

        for registro in registros:
            for vencimento in registro["vencimentos"]:
                if vencimento["data"] != cabecalho:
                    continue

                itens.append({
                    "supervisor": registro["supervisor"],
                    "subsupervisor": registro["subsupervisor"],
                    "comunidade": registro["comunidade"],
                    "qtde": registro["qtde"],
                    "valor": vencimento["valor"],
                })

                total_vencimento += vencimento["valor"]
                pessoas += registro["qtde"]

        if itens:
            resumo_vencimentos.append({
                "data": cabecalho,
                "total": total_vencimento,
                "liderancas": len(itens),
                "pessoas": pessoas,
                "itens": itens,
            })

    return {
        "tipo": "pagamentos_liderancas",
        "titulo": "Relatório de Pagamentos das Lideranças",
        "total_registros": len(registros),
        "total_liderancas": len(registros),
        "total_previsto": total_previsto,
        "total_pago": total_pago,
        "total_resta_pagar": total_resta,
        "total_pessoas": total_pessoas,
        "filtros": {
            "supervisor": limpar_texto(supervisor),
            "subsupervisor": limpar_texto(subsupervisor),
            "comunidade": limpar_texto(comunidade),
        },
        "registros": registros,
        "vencimentos": resumo_vencimentos,
    }


def gerar_pdf_relatorio_pagamentos(resultado_relatorio):
    """Gera PDF A4 retrato com visual de painel: cards, cabeçalhos azuis e vencimentos destacados."""
    buffer = BytesIO()

    AZUL = colors.HexColor("#0B3478")
    AZUL2 = colors.HexColor("#1D5FD0")
    VERDE = colors.HexColor("#237A34")
    LARANJA = colors.HexColor("#D96600")
    VERMELHO = colors.HexColor("#C62828")
    CINZA = colors.HexColor("#D7DCE3")
    CINZA_CLARO = colors.HexColor("#F5F7FA")
    TEXTO = colors.HexColor("#101828")

    documento = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=0.55 * cm, leftMargin=0.55 * cm,
        topMargin=0.60 * cm, bottomMargin=0.75 * cm,
        title="Relatório de Pagamentos das Lideranças"
    )

    base = getSampleStyleSheet()
    titulo = ParagraphStyle("PagTitulo", parent=base["Heading1"], fontName="Helvetica-Bold",
                            fontSize=16, leading=18, alignment=TA_CENTER, textColor=AZUL,
                            spaceAfter=4)
    pequeno = ParagraphStyle("PagPequeno", parent=base["Normal"], fontName="Helvetica",
                             fontSize=7.8, leading=9.2, textColor=TEXTO)
    pequeno_b = ParagraphStyle("PagPequenoB", parent=pequeno, fontName="Helvetica-Bold")
    celula = ParagraphStyle("PagCelula", parent=pequeno, fontSize=7.6, leading=8.8)
    celula_b = ParagraphStyle("PagCelulaB", parent=celula, fontName="Helvetica-Bold", textColor=colors.white)
    centro = ParagraphStyle("PagCentro", parent=celula, alignment=TA_CENTER)
    centro_b = ParagraphStyle("PagCentroB", parent=celula_b, alignment=TA_CENTER)
    secao = ParagraphStyle("PagSecao", parent=base["Heading2"], fontName="Helvetica-Bold",
                           fontSize=11.5, leading=13, textColor=AZUL, spaceBefore=3, spaceAfter=3)
    card_rotulo = ParagraphStyle("PagCardRot", parent=base["Normal"], fontName="Helvetica-Bold",
                                 fontSize=7.5, leading=9, alignment=TA_CENTER)
    card_valor = ParagraphStyle("PagCardVal", parent=base["Normal"], fontName="Helvetica-Bold",
                                fontSize=11.5, leading=13.5, alignment=TA_CENTER, textColor=TEXTO)

    elementos = [Paragraph("RELATÓRIO DE PAGAMENTOS DAS LIDERANÇAS", titulo)]

    # Linha de geração e filtros
    filtros = resultado_relatorio.get("filtros", {})
    partes = []
    for rotulo, chave in (("Supervisor", "supervisor"), ("Subsupervisor", "subsupervisor"), ("Comunidade", "comunidade")):
        valor = limpar_texto(filtros.get(chave, ""))
        if valor:
            partes.append(f"<b>{rotulo}:</b> {valor}")
    linha_info = "Gerado em " + datetime.now().strftime("%d/%m/%Y %H:%M")
    if partes:
        linha_info += " &nbsp;&nbsp; | &nbsp;&nbsp; " + " &nbsp; | &nbsp; ".join(partes)
    elementos += [Paragraph(linha_info, pequeno), Spacer(1, 0.12*cm)]

    # Cards do resumo
    cards = [
        ("LIDERANÇAS", str(resultado_relatorio.get("total_liderancas", 0)), AZUL2),
        ("PESSOAS", str(resultado_relatorio.get("total_pessoas", 0)), VERDE),
        ("TOTAL PREVISTO", _formatar_moeda_pagamentos(resultado_relatorio.get("total_previsto", 0)), LARANJA),
        ("PAGO", _formatar_moeda_pagamentos(resultado_relatorio.get("total_pago", 0)), VERDE),
        ("RESTA PAGAR", _formatar_moeda_pagamentos(resultado_relatorio.get("total_resta_pagar", 0)), VERMELHO),
    ]
    card_data = [[Paragraph(f'<font color="{cor.hexval()}"><b>{rot}</b></font>', card_rotulo) for rot, val, cor in cards],
                 [Paragraph(val, card_valor) for rot, val, cor in cards]]
    cards_t = Table(card_data, colWidths=[3.78*cm]*5, rowHeights=[0.48*cm, 0.70*cm])
    cards_t.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.65, CINZA), ("INNERGRID", (0,0), (-1,-1), 0.35, CINZA),
        ("BACKGROUND", (0,0), (-1,-1), colors.white),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 2), ("RIGHTPADDING", (0,0), (-1,-1), 2),
        ("TOPPADDING", (0,0), (-1,-1), 2), ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    elementos += [cards_t, Spacer(1, 0.18*cm), Paragraph("PAGAMENTOS POR LIDERANÇA", secao)]

    registros = resultado_relatorio.get("registros", [])
    if registros:
        dados = [[Paragraph("SUPERVISOR", centro_b), Paragraph("SUBSUPERVISOR", centro_b),
                  Paragraph("COMUNIDADE", centro_b), Paragraph("QTDE", centro_b),
                  Paragraph("TOTAL", centro_b), Paragraph("PAGO", centro_b), Paragraph("RESTA", centro_b)]]
        for r in registros:
            dados.append([
                Paragraph(r["supervisor"] or "—", celula), Paragraph(r["subsupervisor"] or "—", celula),
                Paragraph(r["comunidade"] or "—", celula), Paragraph(str(r["qtde"]), centro),
                Paragraph(_formatar_moeda_pagamentos(r["total"]), centro),
                Paragraph(_formatar_moeda_pagamentos(r["pago"]), centro),
                Paragraph(_formatar_moeda_pagamentos(r["resta_pagar"]), centro),
            ])
        t = Table(dados, colWidths=[3.35*cm, 3.0*cm, 3.45*cm, 1.15*cm, 2.65*cm, 2.65*cm, 2.65*cm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), AZUL), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("GRID", (0,0), (-1,-1), 0.28, CINZA), ("BOX", (0,0), (-1,-1), 0.5, AZUL),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0), (-1,-1), 2.3), ("RIGHTPADDING", (0,0), (-1,-1), 2.3),
            ("TOPPADDING", (0,0), (-1,-1), 2.1), ("BOTTOMPADDING", (0,0), (-1,-1), 2.1),
        ]))
        elementos += [t, Spacer(1, 0.20*cm), Paragraph("VALORES POR VENCIMENTO", secao)]

        cores = [AZUL2, VERDE, LARANJA, colors.HexColor("#7A3EB1"), colors.HexColor("#00838F")]
        for idx, venc in enumerate(resultado_relatorio.get("vencimentos", [])):
            cor = cores[idx % len(cores)]
            estilo_data = ParagraphStyle(f"DataV{idx}", parent=base["Normal"], fontName="Helvetica-Bold",
                                         fontSize=12, leading=14, textColor=cor)
            estilo_meta = ParagraphStyle(f"MetaV{idx}", parent=base["Normal"], fontName="Helvetica",
                                         fontSize=8.4, leading=10, textColor=TEXTO, alignment=TA_CENTER)
            estilo_total = ParagraphStyle(f"TotV{idx}", parent=estilo_meta, fontName="Helvetica-Bold", textColor=cor)
            cab = Table([[
                Paragraph(venc["data"], estilo_data),
                Paragraph(f'{venc["liderancas"]} liderança(s)', estilo_meta),
                Paragraph(f'{venc["pessoas"]} pessoa(s)', estilo_meta),
                Paragraph(f'TOTAL: {_formatar_moeda_pagamentos(venc["total"])}', estilo_total),
            ]], colWidths=[2.5*cm, 4.2*cm, 4.2*cm, 8.0*cm])
            cab.setStyle(TableStyle([
                ("BOX", (0,0), (-1,-1), 0.75, cor), ("LINEBEFORE", (1,0), (-1,0), 0.35, cor),
                ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#FAFBFD")),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
                ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ]))
            elementos.append(cab)

            hstyle = ParagraphStyle(f"HV{idx}", parent=celula_b, textColor=cor, fontSize=7.8)
            hc = ParagraphStyle(f"HCV{idx}", parent=hstyle, alignment=TA_CENTER)
            vd = [[Paragraph("LIDERANÇA", hstyle), Paragraph("COMUNIDADE", hstyle), Paragraph("QTDE", hc), Paragraph("VALOR", hc)]]
            for item in venc["itens"]:
                lideranca = item["supervisor"] + (f' / {item["subsupervisor"]}' if item["subsupervisor"] else "")
                vd.append([Paragraph(lideranca or "—", celula), Paragraph(item["comunidade"] or "—", celula),
                           Paragraph(str(item["qtde"]), centro), Paragraph(_formatar_moeda_pagamentos(item["valor"]), centro)])
            tv = Table(vd, colWidths=[6.55*cm, 6.25*cm, 2.0*cm, 4.1*cm], repeatRows=1)
            tv.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), CINZA_CLARO), ("GRID", (0,0), (-1,-1), 0.28, CINZA),
                ("BOX", (0,0), (-1,-1), 0.55, cor), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("LEFTPADDING", (0,0), (-1,-1), 3), ("RIGHTPADDING", (0,0), (-1,-1), 3),
                ("TOPPADDING", (0,0), (-1,-1), 2.2), ("BOTTOMPADDING", (0,0), (-1,-1), 2.2),
            ]))
            elementos += [tv, Spacer(1, 0.16*cm)]
    else:
        elementos.append(Paragraph("Nenhum pagamento encontrado.", pequeno))

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(0.65*cm, 0.38*cm, "Relatório de Pagamentos das Lideranças")
        canvas.drawRightString(A4[0]-0.65*cm, 0.38*cm, f"Página {doc.page}")
        canvas.restoreState()

    documento.build(elementos, onFirstPage=rodape, onLaterPages=rodape)
    pdf = buffer.getvalue(); buffer.close(); return pdf
