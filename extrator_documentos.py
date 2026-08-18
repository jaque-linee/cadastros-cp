import re
import unicodedata


# ============================================================
# FUNÇÕES BÁSICAS
# ============================================================

def remover_acentos(texto):
    texto = str(texto or "")

    return "".join(
        caractere
        for caractere in unicodedata.normalize(
            "NFD",
            texto
        )
        if unicodedata.category(
            caractere
        ) != "Mn"
    )


def normalizar_texto(texto):
    texto = remover_acentos(
        texto
    ).upper()

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


def somente_numeros(valor):
    return re.sub(
        r"\D",
        "",
        str(valor or "")
    )


# ============================================================
# IDENTIFICAÇÃO DO TIPO DE DOCUMENTO
# ============================================================

def identificar_documentos(texto):
    """
    Identifica quais documentos aparecem no texto.

    Um mesmo PDF pode conter vários documentos.
    Exemplo:
        RG + TÍTULO + COMPROVANTE

    Retorna uma lista.
    """

    texto_norm = normalizar_texto(
        texto
    )

    documentos = []

    # --------------------------------------------------------
    # TÍTULO ELEITORAL
    # --------------------------------------------------------

    sinais_titulo = [
        "TITULO ELEITORAL",
        "JUSTICA ELEITORAL",
        "NOME DO ELEITOR",
        "ZONA",
        "SECAO",
        "INSCRICAO"
    ]

    pontos_titulo = sum(
        1
        for sinal in sinais_titulo
        if sinal in texto_norm
    )

    if pontos_titulo >= 2:
        documentos.append(
            "TITULO_ELEITORAL"
        )

    # --------------------------------------------------------
    # CARTEIRA DE IDENTIDADE / RG / CIN
    # --------------------------------------------------------

    sinais_identidade = [
        "CARTEIRA DE IDENTIDADE",
        "REGISTRO GERAL",
        "INSTITUTO DE IDENTIFICACAO",
        "SECRETARIA DE ESTADO DA SEGURANCA",
        "ORGAO EXPEDIDOR",
        "NATURALIDADE"
    ]

    pontos_identidade = sum(
        1
        for sinal in sinais_identidade
        if sinal in texto_norm
    )

    if pontos_identidade >= 2:
        documentos.append(
            "IDENTIDADE"
        )

    # --------------------------------------------------------
    # CNH
    # --------------------------------------------------------

    sinais_cnh = [
        "CARTEIRA NACIONAL DE HABILITACAO",
        "PERMISSAO PARA DIRIGIR",
        "VALIDADE",
        "HABILITACAO",
        "ACC"
    ]

    pontos_cnh = sum(
        1
        for sinal in sinais_cnh
        if sinal in texto_norm
    )

    if (
        "CARTEIRA NACIONAL DE HABILITACAO"
        in texto_norm
        or pontos_cnh >= 3
    ):
        documentos.append(
            "CNH"
        )

    # --------------------------------------------------------
    # COMPROVANTE DE ENDEREÇO
    # --------------------------------------------------------

    sinais_endereco = [
        "CEP",
        "ENDERECO",
        "RUA",
        "AVENIDA",
        "TRAVESSA",
        "BAIRRO",
        "FATURA",
        "CONTA",
        "VENCIMENTO"
    ]

    pontos_endereco = sum(
        1
        for sinal in sinais_endereco
        if sinal in texto_norm
    )

    if pontos_endereco >= 3:
        documentos.append(
            "COMPROVANTE_ENDERECO"
        )

    # --------------------------------------------------------
    # CARTÃO SUS
    # --------------------------------------------------------

    sinais_sus = [
        "CARTAO NACIONAL DE SAUDE",
        "CARTAO SUS",
        "SISTEMA UNICO DE SAUDE",
        "CNS"
    ]

    if any(
        sinal in texto_norm
        for sinal in sinais_sus
    ):
        documentos.append(
            "CARTAO_SUS"
        )

    if not documentos:
        documentos.append(
            "DOCUMENTO_NAO_IDENTIFICADO"
        )

    return documentos


# ============================================================
# SEPARAÇÃO APROXIMADA POR DOCUMENTO
# ============================================================

def separar_blocos_documentos(texto):
    """
    Separa o texto em blocos aproximados.

    Não depende de o PDF conter apenas um documento.
    """

    linhas = [
        linha.strip()
        for linha in str(
            texto or ""
        ).splitlines()
        if linha.strip()
    ]

    blocos = {
        "TITULO_ELEITORAL": [],
        "IDENTIDADE": [],
        "CNH": [],
        "COMPROVANTE_ENDERECO": [],
        "OUTROS": []
    }

    bloco_atual = "OUTROS"

    for linha in linhas:

        linha_norm = normalizar_texto(
            linha
        )

        if (
            "TITULO ELEITORAL"
            in linha_norm
            or "JUSTICA ELEITORAL"
            in linha_norm
        ):
            bloco_atual = (
                "TITULO_ELEITORAL"
            )

        elif (
            "CARTEIRA DE IDENTIDADE"
            in linha_norm
            or "REGISTRO GERAL"
            in linha_norm
            or "INSTITUTO DE IDENTIFICACAO"
            in linha_norm
        ):
            bloco_atual = (
                "IDENTIDADE"
            )

        elif (
            "CARTEIRA NACIONAL DE HABILITACAO"
            in linha_norm
        ):
            bloco_atual = "CNH"

        elif (
            "COMPROVANTE DE ENDERECO"
            in linha_norm
            or "COMPROVANTE DE RESIDENCIA"
            in linha_norm
        ):
            bloco_atual = (
                "COMPROVANTE_ENDERECO"
            )

        blocos[
            bloco_atual
        ].append(
            linha
        )

    return {
        chave: "\n".join(
            linhas_bloco
        ).strip()
        for chave, linhas_bloco
        in blocos.items()
        if linhas_bloco
    }


# ============================================================
# RESULTADO INICIAL
# ============================================================

def analisar_documentos(texto):
    """
    Função principal deste módulo.

    Por enquanto apenas identifica e separa.

    A extração específica dos campos será adicionada
    posteriormente, documento por documento.
    """

    documentos = identificar_documentos(
        texto
    )

    blocos = separar_blocos_documentos(
        texto
    )

    return {
        "documentos":
            documentos,

        "blocos":
            blocos
    }
