import os

from flask import Flask, request, jsonify
from flask_cors import CORS

from mobile_api import processar_foto_mobile


# ============================================================
# BASE MOBILE - SERVIDOR HTTP
# ============================================================

app = Flask(__name__)

# Permite que o mobile.html hospedado no GitHub Pages
# converse com esta API.
CORS(app)


# ============================================================
# TESTE DA API
# ============================================================

@app.route("/", methods=["GET"])
def inicio():
    return jsonify(
        {
            "sucesso": True,
            "mensagem": "BASE Mobile API funcionando."
        }
    )


# ============================================================
# RECEBER FOTO E EXECUTAR OCR
# ============================================================

@app.route("/consultar", methods=["POST"])
def consultar():

    try:

        if "foto" not in request.files:
            return jsonify(
                {
                    "sucesso": False,
                    "mensagem": "Nenhuma foto foi enviada."
                }
            ), 400

        foto = request.files["foto"]

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

        resultado = processar_foto_mobile(
            conteudo=conteudo,
            nome=foto.filename,
            tipo=foto.content_type or "image/jpeg"
        )

        return jsonify(
            resultado
        )

    except Exception as erro:

        return jsonify(
            {
                "sucesso": False,
                "mensagem": "Erro interno: " + str(erro)
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
