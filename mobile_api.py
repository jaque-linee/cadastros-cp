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

    def getvalue(
        self
    ):
        return self._arquivo.getvalue()


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

    Usa exatamente o mesmo motor do sistema principal:

    FOTO
      ↓
    ler_documento()
      ↓
    texto + itens + tipo_leitura
      ↓
    extrair_dados(texto, itens, tipo_leitura)
      ↓
    dados encontrados
    """

    if not conteudo:
        return {
            "sucesso": False,
            "mensagem": "Nenhuma imagem recebida.",
            "titulo": "",
            "dados": {}
        }

    try:

        # ====================================================
        # 1. PREPARAR ARQUIVO
        # ====================================================

        arquivo = ArquivoMobile(
            conteudo=conteudo,
            nome=nome,
            tipo=tipo
        )

        # ====================================================
        # 2. USAR O MESMO LEITOR DO STREAMLIT
        #
        # ler_documento() retorna:
        #
        # texto
        # itens
        # tipo_leitura
        # ====================================================

        resultado_leitura = ler_documento(
            arquivo
        )

        # ====================================================
        # 3. VALIDAR RETORNO
        # ====================================================

        if not isinstance(
            resultado_leitura,
            tuple
        ):
            return {
                "sucesso": False,
                "mensagem": (
                    "O leitor retornou um formato inesperado."
                ),
                "titulo": "",
                "dados": {}
            }

        if len(
            resultado_leitura
        ) < 3:
            return {
                "sucesso": False,
                "mensagem": (
                    "O leitor não retornou todas as "
                    "informações necessárias."
                ),
                "titulo": "",
                "dados": {}
            }

        # ====================================================
        # 4. PEGAR OS 3 RETORNOS DO MOTOR
        # ====================================================

        texto = (
            resultado_leitura[0]
            or ""
        )

        itens = (
            resultado_leitura[1]
            or []
        )

        tipo_leitura = (
            resultado_leitura[2]
            or ""
        )

        # ====================================================
        # 5. EXTRAIR DADOS
        #
        # ASSINATURA CORRETA DO SEU MOTOR:
        #
        # extrair_dados(
        #     texto,
        #     itens,
        #     tipo_leitura
        # )
        # ====================================================

        dados = extrair_dados(
            texto,
            itens,
            tipo_leitura
        )

        if not isinstance(
            dados,
            dict
        ):
            dados = {}

        # ====================================================
        # 6. NORMALIZAR TÍTULO
        # ====================================================

        titulo = somente_numeros(
            dados.get(
                "titulo",
                ""
            )
        )

        # ====================================================
        # 7. GARANTIR TÍTULO NORMALIZADO NOS DADOS
        # ====================================================

        if titulo:
            dados["titulo"] = titulo

        # ====================================================
        # 8. RESPOSTA COM TÍTULO LOCALIZADO
        # ====================================================

        if titulo:

            return {
                "sucesso": True,
                "mensagem": "Título localizado.",
                "titulo": titulo,
                "dados": dados,
                "tipo_leitura": tipo_leitura
            }

        # ====================================================
        # 9. FOTO LIDA, MAS SEM TÍTULO
        # ====================================================

        return {
            "sucesso": True,
            "mensagem": (
                "A foto foi lida, mas o título "
                "não foi localizado."
            ),
            "titulo": "",
            "dados": dados,
            "tipo_leitura": tipo_leitura
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
