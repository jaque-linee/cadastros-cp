import re
import requests


def somente_numeros(valor):
    return re.sub(r"\D", "", str(valor or ""))


def normalizar_texto(valor):
    return str(valor or "").strip()


def normalizar_nome(valor):
    return normalizar_texto(valor).upper()


def normalizar_titulo(valor):
    return somente_numeros(valor)


def normalizar_cpf(valor):
    return somente_numeros(valor)


def carregar_base(webhook_url, timeout=15):
    """
    Carrega os registros existentes da aba TABELA
    através do doGet do Google Apps Script.
    """

    try:
        resposta = requests.get(
            webhook_url,
            timeout=timeout
        )

        resposta.raise_for_status()

        dados = resposta.json()

        if not isinstance(dados, list):
            return {
                "sucesso": False,
                "dados": [],
                "mensagem": "Resposta inválida recebida da planilha."
            }

        if (
            len(dados) == 1
            and isinstance(dados[0], dict)
            and dados[0].get("error")
        ):
            return {
                "sucesso": False,
                "dados": [],
                "mensagem": str(
                    dados[0].get("error")
                )
            }

        return {
            "sucesso": True,
            "dados": dados,
            "mensagem": ""
        }

    except requests.exceptions.Timeout:
        return {
            "sucesso": False,
            "dados": [],
            "mensagem": "A consulta à planilha demorou demais."
        }

    except requests.exceptions.RequestException as erro:
        return {
            "sucesso": False,
            "dados": [],
            "mensagem": f"Erro de comunicação com a planilha: {erro}"
        }

    except ValueError:
        return {
            "sucesso": False,
            "dados": [],
            "mensagem": "A planilha retornou uma resposta que não é JSON."
        }

    except Exception as erro:
        return {
            "sucesso": False,
            "dados": [],
            "mensagem": f"Erro ao consultar a planilha: {erro}"
        }

def carregar_concorrentes(webhook_url, timeout=15):
    """
    Carrega as bases da aba CONCORRENTE
    através do doGet do Google Apps Script.

    Retorno esperado:
    {
        "AF": ["titulo1", "titulo2", ...],
        "AT": ["titulo1", "titulo2", ...],
        ...
    }
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

        if not isinstance(dados, dict):
            return {
                "sucesso": False,
                "dados": {},
                "mensagem": (
                    "Resposta inválida recebida "
                    "da aba CONCORRENTE."
                )
            }

        if dados.get("error"):
            return {
                "sucesso": False,
                "dados": {},
                "mensagem": str(
                    dados.get("error")
                )
            }

        bases = {}

        for nome_base, titulos in dados.items():

            nome_base = str(
                nome_base or ""
            ).strip().upper()

            if not nome_base:
                continue

            if not isinstance(titulos, list):
                continue

            titulos_normalizados = set()

            for titulo in titulos:

                titulo_normalizado = normalizar_titulo(
                    titulo
                )

                if titulo_normalizado:
                    titulos_normalizados.add(
                        titulo_normalizado
                    )

            bases[nome_base] = titulos_normalizados

        return {
            "sucesso": True,
            "dados": bases,
            "mensagem": ""
        }

    except requests.exceptions.Timeout:
        return {
            "sucesso": False,
            "dados": {},
            "mensagem": (
                "A consulta à aba CONCORRENTE "
                "demorou demais."
            )
        }

    except requests.exceptions.RequestException as erro:
        return {
            "sucesso": False,
            "dados": {},
            "mensagem": (
                "Erro de comunicação com a "
                f"aba CONCORRENTE: {erro}"
            )
        }

    except ValueError:
        return {
            "sucesso": False,
            "dados": {},
            "mensagem": (
                "A aba CONCORRENTE retornou "
                "uma resposta que não é JSON."
            )
        }

    except Exception as erro:
        return {
            "sucesso": False,
            "dados": {},
            "mensagem": (
                "Erro ao consultar as bases "
                f"concorrentes: {erro}"
            )
        }

def carregar_pagamentos_liderancas(webhook_url, timeout=15):
    """
    Carrega a aba PAGAMENTOS LIDERANÇAS pelo Apps Script.

    O Apps Script devolve uma lista de registros usando os próprios
    cabeçalhos da planilha, inclusive as colunas de datas.
    """
    try:
        resposta = requests.get(
            webhook_url,
            params={"acao": "pagamentos_liderancas"},
            timeout=timeout,
        )
        resposta.raise_for_status()

        dados = resposta.json()

        if isinstance(dados, dict) and dados.get("error"):
            return {
                "sucesso": False,
                "dados": [],
                "mensagem": str(dados.get("error", "")).strip()
                or "Não foi possível carregar os pagamentos.",
            }

        if not isinstance(dados, list):
            return {
                "sucesso": False,
                "dados": [],
                "mensagem": "Resposta inválida ao carregar os pagamentos.",
            }

        return {
            "sucesso": True,
            "dados": dados,
            "mensagem": "",
        }

    except Exception as erro:
        return {
            "sucesso": False,
            "dados": [],
            "mensagem": f"Erro ao carregar pagamentos: {erro}",
        }



def carregar_liderancas_controle(webhook_url, timeout=15):
    """Carrega a aba LIDERANÇAS CONTROLE para obter a coluna ATUAL."""
    try:
        resposta = requests.get(
            webhook_url,
            params={"acao": "liderancas_controle"},
            timeout=timeout,
        )
        resposta.raise_for_status()
        dados = resposta.json()

        if isinstance(dados, dict) and dados.get("error"):
            return {
                "sucesso": False,
                "dados": [],
                "mensagem": str(dados.get("error", "")).strip()
                or "Não foi possível carregar LIDERANÇAS CONTROLE.",
            }

        if not isinstance(dados, list):
            return {
                "sucesso": False,
                "dados": [],
                "mensagem": "Resposta inválida ao carregar LIDERANÇAS CONTROLE.",
            }

        return {"sucesso": True, "dados": dados, "mensagem": ""}

    except Exception as erro:
        return {
            "sucesso": False,
            "dados": [],
            "mensagem": f"Erro ao carregar LIDERANÇAS CONTROLE: {erro}",
        }

def procurar_duplicidade(
    dados_base,
    cpf="",
    titulo=""
):
    """
    Procura cadastro existente por CPF OU Título.

    Não considera nome como critério de duplicidade,
    pois pessoas diferentes podem ter nomes iguais.
    """

    cpf_procurado = normalizar_cpf(cpf)
    titulo_procurado = normalizar_titulo(titulo)

    if not cpf_procurado and not titulo_procurado:
        return None

    for registro in dados_base:
        cpf_existente = normalizar_cpf(
            registro.get("cpf", "")
        )

        titulo_existente = normalizar_titulo(
            registro.get("titulo", "")
        )

        encontrou_cpf = (
            bool(cpf_procurado)
            and bool(cpf_existente)
            and cpf_procurado == cpf_existente
        )

        encontrou_titulo = (
            bool(titulo_procurado)
            and bool(titulo_existente)
            and titulo_procurado == titulo_existente
        )

        if encontrou_cpf or encontrou_titulo:
            return registro

    return None


def preparar_payload(
    dados,
    supervisor,
    subsupervisor
):
    """
    Prepara os dados que serão enviados ao Apps Script.

    Nenhum dado é inventado aqui.
    Campo ausente continua vazio.
    """

    payload = {
        "supervisor": normalizar_nome(
            supervisor
        ),
        "subsupervisor": normalizar_nome(
            subsupervisor
        ),
        "nome": normalizar_nome(
            dados.get("nome", "")
        ),
        "cpf": normalizar_cpf(
            dados.get("cpf", "")
        ),
        "rg": normalizar_texto(
            dados.get("rg", "")
        ),
        "data_nascimento": normalizar_texto(
            dados.get("data_nascimento", "")
        ),
        "nome_mae": normalizar_nome(
            dados.get("nome_mae", "")
        ),
        "endereco": normalizar_texto(
            dados.get("endereco", "")
        ),
        "numero": normalizar_texto(
            dados.get("numero", "")
        ),
        "bairro": normalizar_texto(
            dados.get("bairro", "")
        ),
        "cidade": normalizar_nome(
            dados.get("cidade", "")
        ),
        "titulo": normalizar_titulo(
            dados.get("titulo", "")
        ),
        "zona": somente_numeros(
            dados.get("zona", "")
        ),
        "secao": somente_numeros(
            dados.get("secao", "")
        ),
        "comunidade": normalizar_texto(
            dados.get("comunidade", "")
        ),
        "domicilio": normalizar_texto(
            dados.get("domicilio", "")
        ),
        "telefone": normalizar_texto(
            dados.get("telefone", "")
        )
    }

    return payload


def validar_antes_de_salvar(dados):
    """
    Regra mínima do cadastro automático:

    Nome
    + Nascimento
    + Nome da mãe
    + CPF OU Título
    """

    faltando = []

    nome = normalizar_texto(
        dados.get("nome", "")
    )

    nascimento = normalizar_texto(
        dados.get("data_nascimento", "")
    )

    nome_mae = normalizar_texto(
        dados.get("nome_mae", "")
    )

    cpf = normalizar_cpf(
        dados.get("cpf", "")
    )

    titulo = normalizar_titulo(
        dados.get("titulo", "")
    )

    if not nome:
        faltando.append("NOME")

    if not nascimento:
        faltando.append("NASCIMENTO")

    if not nome_mae:
        faltando.append("NOME DA MÃE")

    if not cpf and not titulo:
        faltando.append("CPF OU TÍTULO")

    return {
        "valido": len(faltando) == 0,
        "faltando": faltando
    }


def salvar_cadastro(
    webhook_url,
    dados,
    supervisor,
    subsupervisor,
    dados_base=None,
    timeout=30
):
    """
    Fluxo completo:

    1. valida os campos obrigatórios;
    2. consulta/verifica duplicidade;
    3. envia o cadastro ao Apps Script;
    4. devolve o resultado ao app.py.
    """

    validacao = validar_antes_de_salvar(
        dados
    )

    if not validacao["valido"]:
        return {
            "status": "CONFERIR",
            "mensagem": (
                "Faltam dados obrigatórios: "
                + ", ".join(
                    validacao["faltando"]
                )
            ),
            "registro": None
        }

    if dados_base is None:
        consulta = carregar_base(
            webhook_url
        )

        if not consulta["sucesso"]:
            return {
                "status": "ERRO",
                "mensagem": consulta["mensagem"],
                "registro": None
            }

        dados_base = consulta["dados"]

    duplicado = procurar_duplicidade(
        dados_base,
        cpf=dados.get("cpf", ""),
        titulo=dados.get("titulo", "")
    )

    if duplicado:
        return {
            "status": "DUPLICADO",
            "mensagem": "Pessoa já cadastrada na TABELA.",
            "registro": duplicado
        }

    payload = preparar_payload(
        dados,
        supervisor,
        subsupervisor
    )

    try:
        resposta = requests.post(
            webhook_url,
            json=payload,
            timeout=timeout
        )

        resposta.raise_for_status()

        retorno = resposta.json()

        status = str(
            retorno.get("status", "")
        ).strip().upper()

        mensagem = str(
            retorno.get(
                "mensagem",
                ""
            )
        ).strip()

        if status == "SUCESSO":
            return {
                "status": "SUCESSO",
                "mensagem": (
                    mensagem
                    or "Cadastro salvo com sucesso."
                ),
                "registro": payload
            }

        return {
            "status": "ERRO",
            "mensagem": (
                mensagem
                or "O Apps Script recusou o cadastro."
            ),
            "registro": None
        }

    except requests.exceptions.Timeout:
        return {
            "status": "ERRO",
            "mensagem": (
                "O envio para a planilha demorou demais."
            ),
            "registro": None
        }

    except requests.exceptions.RequestException as erro:
        return {
            "status": "ERRO",
            "mensagem": (
                f"Erro de comunicação com a planilha: {erro}"
            ),
            "registro": None
        }

    except ValueError:
        return {
            "status": "ERRO",
            "mensagem": (
                "O Apps Script retornou uma resposta inválida."
            ),
            "registro": None
        }

    except Exception as erro:
        return {
            "status": "ERRO",
            "mensagem": (
                f"Erro ao salvar cadastro: {erro}"
            ),
            "registro": None
        }

# ============================================================
# RASCUNHO PERSISTENTE DO LOTE
# ============================================================

def salvar_rascunho_item(
    webhook_url,
    lote_id,
    item,
    supervisor,
    subsupervisor,
    comunidade,
    timeout=20
):
    """Grava/atualiza um documento do lote na aba RASCUNHOS_LOTE."""
    try:
        resposta = requests.post(
            webhook_url,
            json={
                "acao": "salvar_rascunho_item",
                "lote_id": str(lote_id or ""),
                "supervisor": normalizar_nome(supervisor),
                "subsupervisor": normalizar_nome(subsupervisor),
                "comunidade": normalizar_texto(comunidade),
                "arquivo": str(item.get("Arquivo", "") or ""),
                "item": item,
            },
            timeout=timeout
        )
        resposta.raise_for_status()
        retorno = resposta.json()
        return {
            "sucesso": str(retorno.get("status", "")).upper() == "SUCESSO",
            "mensagem": str(retorno.get("mensagem", "") or "")
        }
    except Exception as erro:
        return {
            "sucesso": False,
            "mensagem": f"Não foi possível proteger o rascunho: {erro}"
        }


def carregar_ultimo_rascunho(
    webhook_url,
    supervisor,
    subsupervisor,
    timeout=20
):
    """Recupera o lote pendente mais recente deste supervisor/sub."""
    try:
        resposta = requests.get(
            webhook_url,
            params={
                "acao": "rascunho_ultimo",
                "supervisor": normalizar_nome(supervisor),
                "subsupervisor": normalizar_nome(subsupervisor),
            },
            timeout=timeout
        )
        resposta.raise_for_status()
        retorno = resposta.json()
        return {
            "sucesso": bool(retorno.get("sucesso")),
            "lote_id": str(retorno.get("lote_id", "") or ""),
            "comunidade": str(retorno.get("comunidade", "") or ""),
            "resultados": retorno.get("resultados", []) or [],
            "mensagem": str(retorno.get("mensagem", "") or "")
        }
    except Exception as erro:
        return {
            "sucesso": False,
            "lote_id": "",
            "comunidade": "",
            "resultados": [],
            "mensagem": f"Não foi possível recuperar o rascunho: {erro}"
        }


def excluir_rascunho_lote(webhook_url, lote_id, timeout=20):
    """Apaga o rascunho depois que a usuária finaliza o lote."""
    try:
        resposta = requests.post(
            webhook_url,
            json={
                "acao": "excluir_rascunho_lote",
                "lote_id": str(lote_id or "")
            },
            timeout=timeout
        )
        resposta.raise_for_status()
        retorno = resposta.json()
        return str(retorno.get("status", "")).upper() == "SUCESSO"
    except Exception:
        return False
