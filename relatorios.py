# ============================================================
# RELATÓRIOS
# ============================================================

from io import BytesIO
from datetime import datetime
import html

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


