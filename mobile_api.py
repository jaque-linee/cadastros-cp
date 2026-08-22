import io
import re

from processamento_documentos import (
    ler_documento,
    extrair_dados,
)


# ============================================================
# BASE MOBILE
# PONTE ENTRE A FOTO E O MOTOR DE LEITURA EXISTENTE
# ============================================================


def somente_numeros(valor):
    """
    Mantém somente números.
    """
    return re.sub(
        r"\D",
        "",
        str(valor or "")
    )


# ============================================================
# ARQUIVO RECEBIDO PELO MOBILE
# ============================================================

class ArquivoMobile:
    """
    Adapta os bytes recebidos pelo Mobile para o formato
    esperado pelo processamento_documentos.py.
    """

    def __init__(
        self,
        conteudo,
        nome="documento.jpg",
        tipo="image/jpeg"
    ):
        self._arquivo = io.BytesIO(
            conteudo
        )

        self.name = nome
        self.type = tipo

    def read(
        self,
        *args,
        **kwargs
    ):
        return self._arquivo.read(
            *args,
            **kwargs
        )

    def seek(
        self,
        *args,
        **kwargs
    ):
        return self._arquivo.seek(
            *args,
            **kwargs
        )

    def tell(
        self
    ):
        return self._arquivo.tell()


# ============================================================
# PROCESSAR FOTO
# ============================================================

def processar_foto_mobile(
    conteudo,
    nome="documento.jpg",
    tipo="image/jpeg"
):
    """
    Recebe uma foto enviada pelo BASE Mobile.

    Fluxo:

    FOTO
      ↓
    ler_documento()
      ↓
    extrair_dados()
      ↓
    devolve título e demais dados encontrados
    """

    if not conteudo:
        return {
            "sucesso": False,
            "mensagem": "Nenhuma imagem recebida.",
            "titulo": "",
            "dados": {}
        }

    try:

        arquivo = ArquivoMobile(
            conteudo=conteudo,
            nome=nome,
            tipo=tipo
        )

        # --------------------------------------------
        # OCR EXISTENTE
        # --------------------------------------------

        resultado_leitura = ler_documento(
            arquivo
        )

        # --------------------------------------------
        # ACEITA OS FORMATOS QUE O MOTOR POSSA RETORNAR
        # --------------------------------------------

        texto = ""
        blocos = []

        if isinstance(
            resultado_leitura,
            tuple
        ):

            if len(
                resultado_leitura
            ) >= 1:
                texto = (
                    resultado_leitura[0]
                    or ""
                )

            if len(
                resultado_leitura
            ) >= 2:
                blocos = (
                    resultado_leitura[1]
                    or []
                )

        elif isinstance(
            resultado_leitura,
            dict
        ):

            texto = (
                resultado_leitura.get(
                    "texto",
                    ""
                )
                or ""
            )

            blocos = (
                resultado_leitura.get(
                    "blocos",
                    []
                )
                or []
            )

        else:
            texto = str(
                resultado_leitura
                or ""
            )

        # --------------------------------------------
        # EXTRAÇÃO EXISTENTE
        # --------------------------------------------

        try:

            dados = extrair_dados(
                texto,
                blocos
            )

        except TypeError:

            # Compatibilidade caso a função atual
            # aceite somente o texto.

            dados = extrair_dados(
                texto
            )

        if not isinstance(
            dados,
            dict
        ):
            dados = {}

        # --------------------------------------------
        # TÍTULO
        # --------------------------------------------

        titulo = somente_numeros(
            dados.get(
                "titulo",
                ""
            )
        )

        # --------------------------------------------
        # RESPOSTA
        # --------------------------------------------

        if titulo:

            return {
                "sucesso": True,
                "mensagem": "Título localizado.",
                "titulo": titulo,
                "dados": dados
            }

        return {
            "sucesso": True,
            "mensagem": (
                "A foto foi lida, mas o título "
                "não foi localizado."
            ),
            "titulo": "",
            "dados": dados
        }

    except Exception as erro:

        return {
            "sucesso": False,
            "mensagem": (
                "Erro ao processar a imagem: "
                + str(erro)
            ),
            "titulo": "",
            "dados": {}
        }
