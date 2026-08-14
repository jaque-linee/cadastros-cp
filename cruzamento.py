import re
import requests


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
    Normaliza o título para comparação de forma segura,
    removendo qualquer parte decimal (.0) que o Excel/Sheets adicione.
    """
    if valor is None:
        return ""
    
    # Converte para string e remove ponto decimal indesejado (ex: 123.0 vira 123)
    texto = str(valor).strip().split('.')[0]
    
    # Extrai apenas os números
    titulo = re.sub(r"\D", "", texto)

    if not titulo:
        return ""

    return titulo.lstrip("0") or "0"


# ============================================================
# 2. CARREGAR BASES DA ABA CONCORRENTE
# ============================================================

def carregar_bases(
    webhook_url,
    timeout=20
):
    """
    Carrega dinamicamente todas as bases existentes
    na aba CONCORRENTE através do Apps Script.

    A linha 1 da planilha define os nomes das bases.
    Nenhum nome ou quantidade de colunas é fixado.
    """

    try:
        resposta = requests.get(
            webhook_url,
            params={
                "acao": "concorrentes"
            },
            timeout=timeout
        )

        resposta.raise_for_status()

        dados = resposta.json()

        if not isinstance(
            dados,
            dict
        ):
            return {
                "sucesso": False,
                "bases": {},
                "mensagem": (
                    "Resposta inválida recebida "
                    "da aba CONCORRENTE."
                )
            }

        return {
            "sucesso": True,
            "bases": dados,
            "mensagem": ""
        }

    except requests.exceptions.Timeout:
        return {
            "sucesso": False,
            "bases": {},
            "mensagem": (
                "A consulta à aba CONCORRENTE "
                "demorou demais."
            )
        }

    except requests.exceptions.RequestException as erro:
        return {
            "sucesso": False,
            "bases": {},
            "mensagem": (
                "Erro de comunicação com "
                f"a planilha: {erro}"
            )
        }

    except ValueError:
        return {
            "sucesso": False,
            "bases": {},
            "mensagem": (
                "A aba CONCORRENTE retornou "
                "uma resposta inválida."
            )
        }

    except Exception as erro:
        return {
            "sucesso": False,
            "bases": {},
            "mensagem": (
                "Erro ao carregar as bases: "
                f"{erro}"
            )
        }


# ============================================================
# 3. PROCURAR TÍTULO NAS BASES
# ============================================================

def buscar_titulo(
    titulo,
    bases
):
    """
    Procura o título em todas as bases.

    Retorna somente os nomes das bases
    onde o título foi encontrado.
    """

    titulo_procurado = normalizar_titulo(
        titulo
    )

    if not titulo_procurado:
        return []

    if not isinstance(
        bases,
        dict
    ):
        return []

    encontradas = []

    for nome_base, titulos in bases.items():

        nome_base = str(
            nome_base or ""
        ).strip()

        if not nome_base:
            continue

        if not isinstance(
            titulos,
            list
        ):
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
                    nome_base
                )

                break

    return encontradas


# ============================================================
# 4. FORMATAR RESULTADO
# ============================================================

def formatar_bases_encontradas(
    bases_encontradas
):
    """
    Exemplo:

    ["AF", "MC", "PB"]

    vira:

    AF | MC | PB
    """

    if not bases_encontradas:
        return ""

    return " | ".join(
        str(base).strip()
        for base in bases_encontradas
        if str(base).strip()
    )


# ============================================================
# 5. CRUZAR TÍTULO COM BASES JÁ CARREGADAS
# ============================================================

def cruzar_titulo(
    titulo,
    bases
):
    """
    Cruza um título usando bases
    que já foram carregadas.
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


# ============================================================
# 6. CONSULTAR TÍTULO DIRETAMENTE NA PLANILHA
# ============================================================

def consultar_titulo(
    webhook_url,
    titulo,
    timeout=20
):
    """
    Fluxo completo:

    1. carrega a aba CONCORRENTE;
    2. procura o título;
    3. devolve somente as bases encontradas.
    """

    titulo_normalizado = normalizar_titulo(
        titulo
    )

    if not titulo_normalizado:
        return {
            "sucesso": True,
            "titulo": "",
            "encontrado": False,
            "bases": [],
            "texto": "",
            "mensagem": ""
        }

    consulta = carregar_bases(
        webhook_url,
        timeout=timeout
    )

    if not consulta["sucesso"]:
        return {
            "sucesso": False,
            "titulo": somente_numeros(
                titulo
            ),
            "encontrado": False,
            "bases": [],
            "texto": "",
            "mensagem": consulta[
                "mensagem"
            ]
        }

    resultado = cruzar_titulo(
        titulo,
        consulta["bases"]
    )

    return {
        "sucesso": True,
        "titulo": resultado[
            "titulo"
        ],
        "encontrado": resultado[
            "encontrado"
        ],
        "bases": resultado[
            "bases"
        ],
        "texto": resultado[
            "texto"
        ],
        "mensagem": ""
    }
