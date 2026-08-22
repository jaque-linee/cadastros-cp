import os
import re
import gc
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


def resposta_json(dados, status=200):
    resposta = jsonify(dados)
    resposta.headers["Cache-Control"] = "no-store"
    return resposta, status


# ============================================================
# CONSULTAR TÍTULO NO GOOGLE SHEETS
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

    print(
        "[BASE MOBILE] Consultando título:",
        titulo,
        flush=True
    )

    resposta = requests.get(
        WEBHOOK_URL,
        params={
            "titulo": titulo
        },
        timeout=20
    )

    print(
        "[BASE MOBILE] Apps Script respondeu:",
        resposta.status_code,
        flush=True
    )

    resposta.raise_for_status()

    dados = resposta.json()

    if not isinstance(
        dados,
        dict
    ):
        raise Exception(
            "A consulta da BASE retornou formato inesperado."
        )

    if dados.get("error"):
        raise Exception(
            str(
                dados.get("error")
            )
        )

    return dados


# ============================================================
# TESTE GERAL
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
# TESTE SIMPLES DE RECEBIMENTO DA FOTO
#
# NÃO FAZ OCR.
# Serve apenas para verificar se a foto chega ao Render.
# ============================================================

@app.route(
    "/teste-foto",
    methods=["POST"]
)
def teste_foto():

    try:

        if "foto" not in request.files:

            return resposta_json(
                {
                    "sucesso": False,
                    "etapa": "recebimento",
                    "mensagem": "Nenhuma foto recebida."
                },
                400
            )

        foto = request.files["foto"]

        conteudo = foto.read()

        tamanho = len(
            conteudo
        )

        print(
            "[BASE MOBILE] Foto recebida:",
            foto.filename,
            "-",
            tamanho,
            "bytes",
            flush=True
        )

        del conteudo

        gc.collect()

        return resposta_json(
            {
                "sucesso": True,
                "etapa": "recebimento",
                "mensagem": "Foto recebida pelo Render.",
                "arquivo": foto.filename,
                "tamanho": tamanho
            }
        )

    except Exception as erro:

        print(
            "[BASE MOBILE] ERRO TESTE FOTO:",
            repr(erro),
            flush=True
        )

        return resposta_json(
            {
                "sucesso": False,
                "etapa": "recebimento",
                "mensagem": str(erro)
            },
            500
        )


# ============================================================
# TESTE DIRETO DA BASE
#
# Exemplo:
# /teste-base?titulo=040787661740
#
# NÃO FAZ OCR.
# ============================================================

@app.route(
    "/teste-base",
    methods=["GET"]
)
def teste_base():

    try:

        titulo = somente_numeros(
            request.args.get(
                "titulo",
                ""
            )
        )

        if not titulo:

            return resposta_json(
                {
                    "sucesso": False,
                    "etapa": "base",
                    "mensagem": "Informe um título."
                },
                400
            )

        consulta = consultar_titulo_base(
            titulo
        )

        return resposta_json(
            {
                "sucesso": True,
                "etapa": "base",
                "titulo": titulo,
                "resultado": consulta
            }
        )

    except Exception as erro:

        print(
            "[BASE MOBILE] ERRO BASE:",
            repr(erro),
            flush=True
        )

        return resposta_json(
            {
                "sucesso": False,
                "etapa": "base",
                "mensagem": str(erro)
            },
            500
        )


# ============================================================
# CONSULTA COMPLETA
#
# FOTO
#   ↓
# OCR
#   ↓
# TÍTULO
#   ↓
# GOOGLE SHEETS
# ============================================================

@app.route(
    "/consultar",
    methods=["POST"]
)
def consultar():

    conteudo = None

    try:

        # ----------------------------------------------------
        # 1. RECEBIMENTO
        # ----------------------------------------------------

        print(
            "[BASE MOBILE] ===== NOVA CONSULTA =====",
            flush=True
        )

        if "foto" not in request.files:

            return resposta_json(
                {
                    "sucesso": False,
                    "etapa": "recebimento",
                    "mensagem": "Nenhuma foto foi enviada."
                },
                400
            )


        foto = request.files[
            "foto"
        ]


        if not foto.filename:

            return resposta_json(
                {
                    "sucesso": False,
                    "etapa": "recebimento",
                    "mensagem": "Arquivo inválido."
                },
                400
            )


        conteudo = foto.read()


        if not conteudo:

            return resposta_json(
                {
                    "sucesso": False,
                    "etapa": "recebimento",
                    "mensagem": "A foto recebida está vazia."
                },
                400
            )


        print(
            "[BASE MOBILE] Foto recebida:",
            foto.filename,
            "-",
            len(conteudo),
            "bytes",
            flush=True
        )


        # ----------------------------------------------------
        # 2. OCR
        # ----------------------------------------------------

        print(
            "[BASE MOBILE] Iniciando OCR...",
            flush=True
        )


        resultado = processar_foto_mobile(
            conteudo=conteudo,
            nome=foto.filename,
            tipo=foto.content_type or "image/jpeg"
        )


        print(
            "[BASE MOBILE] OCR finalizado.",
            flush=True
        )


        # Já não precisamos manter os bytes originais
        # da foto depois do OCR.

        conteudo = None

        gc.collect()


        if not isinstance(
            resultado,
            dict
        ):

            return resposta_json(
                {
                    "sucesso": False,
                    "etapa": "ocr",
                    "mensagem": "O OCR retornou formato inválido."
                },
                500
            )


        if not resultado.get(
            "sucesso"
        ):

            resultado[
                "etapa"
            ] = "ocr"

            return resposta_json(
                resultado
            )


        titulo = somente_numeros(
            resultado.get(
                "titulo",
                ""
            )
        )


        print(
            "[BASE MOBILE] Título lido:",
            titulo or "NÃO LOCALIZADO",
            flush=True
        )


        # ----------------------------------------------------
        # 3. SEM TÍTULO
        # ----------------------------------------------------

        if not titulo:

            resultado[
                "cadastrado"
            ] = False

            resultado[
                "cadastro"
            ] = None

            resultado[
                "etapa"
            ] = "ocr"

            return resposta_json(
                resultado
            )


        # ----------------------------------------------------
        # 4. CONSULTA AO SHEETS
        # ----------------------------------------------------

        print(
            "[BASE MOBILE] OCR OK. Iniciando consulta à BASE...",
            flush=True
        )


        consulta_base = consultar_titulo_base(
            titulo
        )


        print(
            "[BASE MOBILE] Consulta à BASE finalizada.",
            flush=True
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
        # 5. CADASTRADO
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
            ] = (
                "Título localizado e cadastrado na BASE."
            )

            resultado[
                "etapa"
            ] = "concluido"


            print(
                "[BASE MOBILE] CADASTRADO:",
                cadastro.get(
                    "nome",
                    ""
                ),
                flush=True
            )


        # ----------------------------------------------------
        # 6. NÃO CADASTRADO
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
            ] = (
                "Título localizado, mas não cadastrado na BASE."
            )

            resultado[
                "etapa"
            ] = "concluido"


            print(
                "[BASE MOBILE] NÃO CADASTRADO.",
                flush=True
            )


        gc.collect()


        return resposta_json(
            resultado
        )


    # ========================================================
    # TIMEOUT DO GOOGLE
    # ========================================================

    except requests.Timeout:

        print(
            "[BASE MOBILE] TIMEOUT NA BASE.",
            flush=True
        )

        return resposta_json(
            {
                "sucesso": False,
                "etapa": "base",
                "mensagem": (
                    "O documento foi lido, mas a consulta "
                    "ao banco de dados demorou demais."
                )
            },
            504
        )


    # ========================================================
    # ERRO DE CONEXÃO COM GOOGLE
    # ========================================================

    except requests.RequestException as erro:

        print(
            "[BASE MOBILE] ERRO DE CONEXÃO COM A BASE:",
            repr(erro),
            flush=True
        )

        return resposta_json(
            {
                "sucesso": False,
                "etapa": "base",
                "mensagem": (
                    "O documento foi lido, mas houve erro "
                    "ao consultar o banco de dados: "
                    + str(erro)
                )
            },
            500
        )


    # ========================================================
    # OUTROS ERROS
    # ========================================================

    except Exception as erro:

        print(
            "[BASE MOBILE] ERRO:",
            repr(erro),
            flush=True
        )

        return resposta_json(
            {
                "sucesso": False,
                "etapa": "servidor",
                "mensagem": (
                    "Erro interno: "
                    + str(erro)
                )
            },
            500
        )


    finally:

        conteudo = None

        gc.collect()


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
