import os
import re
import requests

from flask import Flask, request, jsonify
from flask_cors import CORS

from mobile_api import processar_foto_mobile


# ============================================================
# BASE MOBILE - SERVIDOR HTTP
# ============================================================

app = Flask(__name__)
CORS(app)


# ============================================================
# CONFIGURAÇÃO
# ============================================================

WEBHOOK_URL = os.environ.get(
    "WEBHOOK_URL",
    ""
)


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def somente_numeros(valor):
    return re.sub(
        r"\D",
        "",
        str(valor or "")
    )


def normalizar_titulo(valor):
    """
    Remove pontuação e zeros à esquerda para comparação.
    """

    numero = somente_numeros(
        valor
    )

    if not numero:
        return ""

    normalizado = numero.lstrip("0")

    return normalizado or "0"


# ============================================================
# CARREGAR BASE DO GOOGLE SHEETS
# ============================================================

def carregar_base():

    if not WEBHOOK_URL:
        raise Exception(
            "WEBHOOK_URL não configurado no servidor."
        )

    resposta = requests.get(
        WEBHOOK_URL,
        timeout=20
    )

    resposta.raise_for_status()

    dados = resposta.json()

    if not isinstance(
        dados,
        list
    ):
        raise Exception(
            "A base retornou um formato inesperado."
        )

    return dados


# ============================================================
# PROCURAR TÍTULO NA BASE
# ============================================================

def procurar_titulo(
    titulo,
    base
):

    titulo_procurado = normalizar_titulo(
        titulo
    )

    if not titulo_procurado:
        return None

    for pessoa in base:

        titulo_existente = normalizar_titulo(
            pessoa.get(
                "titulo",
                ""
            )
        )

        if (
            titulo_existente
            and titulo_existente
            == titulo_procurado
        ):
            return pessoa

    return None


# ============================================================
# TESTE DA API
# ============================================================

@app.route(
    "/",
    methods=["GET"]
)
def inicio():

    return jsonify(
        {
            "sucesso": True,
            "mensagem": "BASE Mobile API funcionando."
        }
    )


# ============================================================
# RECEBER FOTO
# OCR + CONSULTA NA BASE
# ============================================================

@app.route(
    "/consultar",
    methods=["POST"]
)
def consultar():

    try:

        # ----------------------------------------------------
        # VALIDAR FOTO
        # ----------------------------------------------------

        if "foto" not in request.files:

            return jsonify(
                {
                    "sucesso": False,
                    "mensagem": "Nenhuma foto foi enviada."
                }
            ), 400


        foto = request.files[
            "foto"
        ]


        if not foto.filename:

            return jsonify(
                {
                    "sucesso": False,
                    "mensagem": "Arquivo inválido."
                }
            ), 400


        conteudo = foto.read()


        if not conteudo:

            return jsonify(
                {
                    "sucesso": False,
                    "mensagem": "A foto recebida está vazia."
                }
            ), 400


        # ----------------------------------------------------
        # OCR
        # ----------------------------------------------------

        resultado = processar_foto_mobile(
            conteudo=conteudo,
            nome=foto.filename,
            tipo=foto.content_type or "image/jpeg"
        )


        if not resultado.get(
            "sucesso"
        ):

            return jsonify(
                resultado
            )


        titulo = somente_numeros(
            resultado.get(
                "titulo",
                ""
            )
        )


        # ----------------------------------------------------
        # NÃO ENCONTROU TÍTULO NA FOTO
        # ----------------------------------------------------

        if not titulo:

            resultado[
                "cadastrado"
            ] = False

            resultado[
                "cadastro"
            ] = None

            return jsonify(
                resultado
            )


        # ----------------------------------------------------
        # CARREGAR BASE
        # ----------------------------------------------------

        base = carregar_base()


        # ----------------------------------------------------
        # PROCURAR TÍTULO
        # ----------------------------------------------------

        cadastro = procurar_titulo(
            titulo,
            base
        )


        # ----------------------------------------------------
        # ENCONTRADO NA BASE
        # ----------------------------------------------------

        if cadastro:

            resultado[
                "cadastrado"
            ] = True

            resultado[
                "cadastro"
            ] = {
                "nome": str(
                    cadastro.get(
                        "nome",
                        ""
                    )
                ).strip(),

                "titulo": str(
                    cadastro.get(
                        "titulo",
                        ""
                    )
                ).strip(),

                "cpf": str(
                    cadastro.get(
                        "cpf",
                        ""
                    )
                ).strip(),

                "supervisor": str(
                    cadastro.get(
                        "supervisor",
                        ""
                    )
                ).strip(),

                "subsupervisor": str(
                    cadastro.get(
                        "subsupervisor",
                        ""
                    )
                ).strip(),

                "comunidade": str(
                    cadastro.get(
                        "comunidade",
                        ""
                    )
                ).strip(),

                "domicilio": str(
                    cadastro.get(
                        "domicilio",
                        ""
                    )
                ).strip(),

                "status": str(
                    cadastro.get(
                        "status",
                        ""
                    )
                ).strip(),

                "situacao": str(
                    cadastro.get(
                        "situacao",
                        ""
                    )
                ).strip()
            }


        # ----------------------------------------------------
        # NÃO ENCONTRADO NA BASE
        # ----------------------------------------------------

        else:

            resultado[
                "cadastrado"
            ] = False

            resultado[
                "cadastro"
            ] = None


        return jsonify(
            resultado
        )


    except requests.RequestException as erro:

        return jsonify(
            {
                "sucesso": False,
                "mensagem": (
                    "O documento foi lido, mas houve erro "
                    "ao consultar o banco de dados: "
                    + str(erro)
                )
            }
        ), 500


    except Exception as erro:

        return jsonify(
            {
                "sucesso": False,
                "mensagem": (
                    "Erro interno: "
                    + str(erro)
                )
            }
        ), 500


# ============================================================
# EXECUÇÃO LOCAL
# ============================================================

if __name__ == "__main__":

    porta = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=porta
    )
