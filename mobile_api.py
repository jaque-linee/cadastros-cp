import io
import re
import gc

from PIL import Image, ImageOps

from processamento_documentos import (
    ler_documento,
    extrair_dados,
)


# ============================================================
# BASE MOBILE
# PONTE ENTRE A FOTO E O MOTOR DE LEITURA EXISTENTE
# ============================================================


def somente_numeros(valor):
    return re.sub(
        r"\D",
        "",
        str(valor or "")
    )


# ============================================================
# PREPARAR IMAGEM PARA O MOBILE
# ============================================================

def preparar_imagem_mobile(
    conteudo,
    largura_maxima=1400
):
    """
    Reduz somente a imagem enviada pelo Mobile.

    O motor OCR continua sendo exatamente o mesmo
    utilizado pelo sistema principal.

    A imagem original do Streamlit não é alterada.
    """

    imagem = Image.open(
        io.BytesIO(conteudo)
    )

    # Corrige orientação de fotos tiradas pelo iPhone.
    imagem = ImageOps.exif_transpose(
        imagem
    )

    # Evita modos de imagem desnecessariamente pesados.
    if imagem.mode != "RGB":
        imagem = imagem.convert(
            "RGB"
        )

    largura, altura = imagem.size

    print(
        "[BASE MOBILE] Imagem original:",
        largura,
        "x",
        altura,
        flush=True
    )

    # --------------------------------------------------------
    # REDUZ APENAS SE A FOTO FOR GRANDE
    # --------------------------------------------------------

    if largura > largura_maxima:

        proporcao = (
            largura_maxima
            / float(largura)
        )

        nova_altura = int(
            altura * proporcao
        )

        imagem = imagem.resize(
            (
                largura_maxima,
                nova_altura
            ),
            Image.Resampling.LANCZOS
        )

    largura_final, altura_final = imagem.size

    print(
        "[BASE MOBILE] Imagem para OCR:",
        largura_final,
        "x",
        altura_final,
        flush=True
    )

    # --------------------------------------------------------
    # CONVERTER NOVAMENTE PARA JPEG
    # --------------------------------------------------------

    buffer = io.BytesIO()

    imagem.save(
        buffer,
        format="JPEG",
        quality=88,
        optimize=True
    )

    conteudo_reduzido = (
        buffer.getvalue()
    )

    imagem.close()
    buffer.close()

    del imagem
    del buffer

    gc.collect()

    print(
        "[BASE MOBILE] Foto preparada:",
        len(conteudo_reduzido),
        "bytes",
        flush=True
    )

    return conteudo_reduzido


# ============================================================
# ARQUIVO RECEBIDO PELO MOBILE
# ============================================================

class ArquivoMobile:

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


    def close(
        self
    ):

        try:
            self._arquivo.close()

        except Exception:
            pass


# ============================================================
# PROCESSAR FOTO
# ============================================================

def processar_foto_mobile(
    conteudo,
    nome="documento.jpg",
    tipo="image/jpeg"
):

    if not conteudo:

        return {
            "sucesso": False,
            "mensagem": "Nenhuma imagem recebida.",
            "titulo": "",
            "dados": {}
        }


    arquivo = None
    conteudo_preparado = None


    try:

        # ====================================================
        # 1. PREPARAR A FOTO
        #
        # SOMENTE MOBILE.
        # NÃO ALTERA O STREAMLIT.
        # ====================================================

        print(
            "[BASE MOBILE] Preparando imagem...",
            flush=True
        )

        conteudo_preparado = (
            preparar_imagem_mobile(
                conteudo
            )
        )


        # ====================================================
        # 2. LIBERAR REFERÊNCIA À FOTO ORIGINAL
        # ====================================================

        conteudo = None

        gc.collect()


        # ====================================================
        # 3. CRIAR ARQUIVO PARA O MOTOR EXISTENTE
        # ====================================================

        arquivo = ArquivoMobile(
            conteudo=conteudo_preparado,
            nome="mobile_ocr.jpg",
            tipo="image/jpeg"
        )


        # ====================================================
        # 4. MESMO OCR DO STREAMLIT
        # ====================================================

        print(
            "[BASE MOBILE] Chamando ler_documento()...",
            flush=True
        )

        resultado_leitura = ler_documento(
            arquivo
        )


        print(
            "[BASE MOBILE] ler_documento() finalizado.",
            flush=True
        )


        # ====================================================
        # 5. VALIDAR RETORNO
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
        # 6. RETORNOS DO MOTOR
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
        # 7. EXTRAÇÃO
        #
        # CONTINUA USANDO O MESMO EXTRATOR DO STREAMLIT.
        # ====================================================

        print(
            "[BASE MOBILE] Extraindo dados...",
            flush=True
        )

        dados = extrair_dados(
            texto,
            itens,
            tipo_leitura
        )

        print(
            "[BASE MOBILE] Extração finalizada.",
            flush=True
        )


        if not isinstance(
            dados,
            dict
        ):

            dados = {}


        # ====================================================
        # 8. TÍTULO
        # ====================================================

        titulo = somente_numeros(
            dados.get(
                "titulo",
                ""
            )
        )


        if titulo:

            dados[
                "titulo"
            ] = titulo


            return {
                "sucesso": True,
                "mensagem": "Título localizado.",
                "titulo": titulo,
                "dados": dados,
                "tipo_leitura": tipo_leitura
            }


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

        print(
            "[BASE MOBILE] ERRO MOBILE API:",
            repr(erro),
            flush=True
        )

        return {
            "sucesso": False,
            "mensagem": (
                "Erro ao processar a imagem: "
                + str(erro)
            ),
            "titulo": "",
            "dados": {}
        }


    finally:

        if arquivo is not None:

            arquivo.close()


        conteudo_preparado = None
        conteudo = None
        arquivo = None

        gc.collect()
