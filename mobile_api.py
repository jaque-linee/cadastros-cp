import io
import re
import gc

from PIL import Image, ImageOps


# ============================================================
# BASE MOBILE
# PONTE ENTRE A FOTO E O MOTOR DE LEITURA EXISTENTE
#
# IMPORTANTE:
# processamento_documentos NÃO é importado aqui no topo.
# Ele só será importado DEPOIS que a imagem estiver preparada.
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
    largura_maxima=1200
):
    """
    Prepara somente a foto recebida pelo Mobile.

    O Streamlit não usa esta função e não é alterado.

    O OCR e o extrator continuam sendo os mesmos
    do processamento_documentos.py.
    """

    print(
        "[BASE MOBILE] Preparando imagem...",
        flush=True
    )

    buffer_entrada = io.BytesIO(
        conteudo
    )

    imagem = Image.open(
        buffer_entrada
    )

    # Corrige orientação gravada pelo iPhone/celular
    imagem = ImageOps.exif_transpose(
        imagem
    )

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
    # REDUZIR RESOLUÇÃO SOMENTE QUANDO NECESSÁRIO
    # --------------------------------------------------------

    maior_lado = max(
        largura,
        altura
    )

    if maior_lado > largura_maxima:

        proporcao = (
            largura_maxima
            / float(maior_lado)
        )

        nova_largura = max(
            1,
            int(
                largura * proporcao
            )
        )

        nova_altura = max(
            1,
            int(
                altura * proporcao
            )
        )

        imagem = imagem.resize(
            (
                nova_largura,
                nova_altura
            ),
            Image.Resampling.LANCZOS
        )

    largura_final, altura_final = (
        imagem.size
    )

    print(
        "[BASE MOBILE] Imagem para OCR:",
        largura_final,
        "x",
        altura_final,
        flush=True
    )

    # --------------------------------------------------------
    # SALVAR UMA VERSÃO LEVE PARA O OCR
    # --------------------------------------------------------

    buffer_saida = io.BytesIO()

    imagem.save(
        buffer_saida,
        format="JPEG",
        quality=85,
        optimize=True
    )

    conteudo_preparado = (
        buffer_saida.getvalue()
    )

    try:
        imagem.close()
    except Exception:
        pass

    try:
        buffer_entrada.close()
    except Exception:
        pass

    try:
        buffer_saida.close()
    except Exception:
        pass

    imagem = None
    buffer_entrada = None
    buffer_saida = None

    gc.collect()

    print(
        "[BASE MOBILE] Foto preparada:",
        len(conteudo_preparado),
        "bytes",
        flush=True
    )

    return conteudo_preparado


# ============================================================
# ARQUIVO COMPATÍVEL COM O MOTOR EXISTENTE
# ============================================================

class ArquivoMobile:

    def __init__(
        self,
        conteudo,
        nome="mobile_ocr.jpg",
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

    arquivo = None
    conteudo_preparado = None

    if not conteudo:

        return {
            "sucesso": False,
            "mensagem": "Nenhuma imagem recebida.",
            "titulo": "",
            "dados": {}
        }

    try:

        # ====================================================
        # 1. PREPARAR FOTO ANTES DE CARREGAR O OCR
        # ====================================================

        conteudo_preparado = (
            preparar_imagem_mobile(
                conteudo
            )
        )

        # Libera a referência local à foto original
        conteudo = None

        gc.collect()


        # ====================================================
        # 2. CRIAR ARQUIVO LEVE
        # ====================================================

        arquivo = ArquivoMobile(
            conteudo=conteudo_preparado,
            nome="mobile_ocr.jpg",
            tipo="image/jpeg"
        )

        # A cópia de bytes já está dentro do ArquivoMobile
        conteudo_preparado = None

        gc.collect()


        # ====================================================
        # 3. SÓ AGORA IMPORTAR O MOTOR DO SISTEMA
        #
        # O STREAMLIT CONTINUA INALTERADO.
        # ====================================================

        print(
            "[BASE MOBILE] Carregando motor OCR...",
            flush=True
        )

        from processamento_documentos import (
            ler_documento,
            extrair_dados,
        )

        print(
            "[BASE MOBILE] Motor OCR carregado.",
            flush=True
        )


        # ====================================================
        # 4. MESMO LER_DOCUMENTO DO STREAMLIT
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
        # 7. EXTRAIR DADOS COM O MESMO EXTRATOR
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
        # 8. NORMALIZAR TÍTULO
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

            print(
                "[BASE MOBILE] Título localizado:",
                titulo,
                flush=True
            )

            return {
                "sucesso": True,
                "mensagem": "Título localizado.",
                "titulo": titulo,
                "dados": dados,
                "tipo_leitura": tipo_leitura
            }


        print(
            "[BASE MOBILE] Título não localizado.",
            flush=True
        )

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

        arquivo = None
        conteudo = None
        conteudo_preparado = None

        gc.collect()
