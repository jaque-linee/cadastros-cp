import re


# ============================================================
# 1. FUNÇÕES BÁSICAS
# ============================================================

def somente_numeros(valor):
    return re.sub(
        r"\D",
        "",
        str(valor or "")
    )


def normalizar_titulo(valor):
    """
    Normaliza o título para comparação.

    Remove:
    - pontos;
    - espaços;
    - traços;
    - outros caracteres não numéricos.

    Também desconsidera zeros à esquerda.
    """

    titulo = somente_numeros(valor)

    if not titulo:
        return ""

    return titulo.lstrip("0") or "0"


# ============================================================
# 2. CRUZAR UM TÍTULO
# ============================================================

def buscar_titulo(
    titulo,
    bases
):
    """
    Procura um título em todas as bases recebidas.

    Formato esperado de 'bases':

    {
        "AF": ["123456789012", "999999999999"],
        "AT": ["111111111111"],
        "MC": ["123456789012"]
    }

    Retorna somente os nomes das bases
    onde o título foi encontrado.

    Exemplo:
        ["AF", "MC"]
    """

    titulo_procurado = normalizar_titulo(
        titulo
    )

    if not titulo_procurado:
        return []

    encontradas = []

    if not isinstance(
        bases,
        dict
    ):
        return encontradas

    for nome_base, titulos in bases.items():

        if not nome_base:
            continue

        if titulos is None:
            continue

        for titulo_base in titulos:

            titulo_existente = normalizar_titulo(
                titulo_base
            )

            if not titulo_existente:
                continue

            if (
                titulo_procurado
                == titulo_existente
            ):
                encontradas.append(
                    str(nome_base).strip()
                )

                break

    return encontradas


# ============================================================
# 3. FORMATAR RESULTADO
# ============================================================

def formatar_bases_encontradas(
    bases_encontradas
):
    """
    Transforma a lista de bases encontradas
    em texto para exibição no app.

    Exemplo:
        ["AF", "MC", "PB"]

    Resultado:
        "AF | MC | PB"
    """

    if not bases_encontradas:
        return ""

    return " | ".join(
        str(base).strip()
        for base in bases_encontradas
        if str(base).strip()
    )


# ============================================================
# 4. CRUZAMENTO COMPLETO
# ============================================================

def cruzar_titulo(
    titulo,
    bases
):
    """
    Executa o cruzamento e devolve
    uma estrutura pronta para o app.py.
    """

    encontradas = buscar_titulo(
        titulo,
        bases
    )

    return {
        "titulo": somente_numeros(
            titulo
        ),
        "encontrado": bool(
            encontradas
        ),
        "bases": encontradas,
        "texto": formatar_bases_encontradas(
            encontradas
        )
    }
