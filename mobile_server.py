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


# ============================================================
# CONSULTAR UM ÚNICO TÍTULO NO GOOGLE SHEETS
# ============================================================

def consultar_titulo_base(titulo):

    if not WEBHOOK_URL:
        raise Exception(
            "WEBHOOK_URL não configurado no servidor."
        )

    titulo = somente_numeros(
        titulo
    )

    if not titulo:
        return {
            "encontrado": False,
            "cadastro": None
        }

    resposta = requests.get(
        WEBHOOK_URL,
        params={
            "titulo": titulo
        },
        timeout=20
    )

    resposta.raise_for_status()

    dados = resposta.json()

    if not isinstance(
        dados,
        dict
    ):
        raise Exception(
            "A consulta da BASE retornou um formato inesperado."
        )

    if dados.get(
        "error"
    ):
        raise Exception(
            str(
                dados.get(
                    "error"
                )
            )
        )

    return dados


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
        # FOTO LIDA, MAS SEM TÍTULO
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
        # CONSULTAR SOMENTE ESTE TÍTULO NO APPS SCRIPT
        # ----------------------------------------------------

        consulta_base = consultar_titulo_base(
            titulo
        )


        encontrado = bool(
            consulta_base.get(
                "encontrado",
                False
            )
        )


        cadastro = consulta_base.get(
            "cadastro"
        )


        # ----------------------------------------------------
        # TÍTULO ENCONTRADO NA BASE
        # ----------------------------------------------------

        if (
            encontrado
            and isinstance(
                cadastro,
                dict
            )
        ):

            resultado[
                "cadastrado"
            ] = True

            resultado[
                "cadastro"
            ] = cadastro

            resultado[
                "mensagem"
            ] = "Título localizado e cadastrado na BASE."


        # ----------------------------------------------------
        # TÍTULO NÃO ENCONTRADO NA BASE
        # ----------------------------------------------------

        else:

            resultado[
                "cadastrado"
            ] = False

            resultado[
                "cadastro"
            ] = None

            resultado[
                "mensagem"
            ] = "Título localizado, mas não cadastrado na BASE."


        return jsonify(
            resultado
        )


    except requests.Timeout:

        return jsonify(
            {
                "sucesso": False,
                "mensagem": (
                    "O documento foi lido, mas a consulta "
                    "ao banco de dados demorou demais."
                )
            }
        ), 504


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
