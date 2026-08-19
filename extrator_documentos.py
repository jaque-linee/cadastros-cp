import re
import unicodedata
from datetime import datetime


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
        if unicodedata.category(caractere) != "Mn"
    )


def normalizar_texto(texto):
    texto = remover_acentos(texto).upper()
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def normalizar_linha(texto):
    texto = remover_acentos(texto).upper()
    texto = re.sub(r"[ \t]+", " ", texto)
    return texto.strip()


def somente_numeros(valor):
    return re.sub(
        r"\D",
        "",
        str(valor or "")
    )


def linhas_texto(texto):
    return [
        linha.strip()
        for linha in str(texto or "").splitlines()
        if linha.strip()
    ]


def resultado_vazio():
    return {
        "nome": "",
        "cpf": "",
        "rg": "",
        "data_nascimento": "",
        "nome_mae": "",
        "titulo": "",
        "zona": "",
        "secao": "",
        "endereco": "",
        "numero": "",
        "bairro": "",
        "cidade": "",
        "telefone": "",
        "nis": "",
        "dap": "",
        "sus": ""
    }


# ============================================================
# VALIDAÇÕES
# ============================================================

def data_valida(valor):
    try:
        datetime.strptime(
            valor,
            "%d/%m/%Y"
        )
        return True

    except Exception:
        return False


def cpf_valido(cpf):
    cpf = somente_numeros(cpf)

    if len(cpf) != 11:
        return False

    if cpf == cpf[0] * 11:
        return False

    try:
        soma = sum(
            int(cpf[i]) * (10 - i)
            for i in range(9)
        )

        digito1 = (
            11 - (soma % 11)
        )

        if digito1 >= 10:
            digito1 = 0

        soma = sum(
            int(cpf[i]) * (11 - i)
            for i in range(10)
        )

        digito2 = (
            11 - (soma % 11)
        )

        if digito2 >= 10:
            digito2 = 0

        return (
            int(cpf[9]) == digito1
            and int(cpf[10]) == digito2
        )

    except Exception:
        return False


def formatar_cpf(cpf):
    cpf = somente_numeros(cpf)

    if len(cpf) != 11:
        return cpf

    return (
        f"{cpf[:3]}."
        f"{cpf[3:6]}."
        f"{cpf[6:9]}-"
        f"{cpf[9:]}"
    )


# ============================================================
# NOMES
# ============================================================

PALAVRAS_PROIBIDAS_NOME = {
    "REPUBLICA",
    "FEDERATIVA",
    "BRASIL",
    "GOVERNO",
    "FEDERAL",
    "ESTADO",
    "SECRETARIA",
    "SEGURANCA",
    "PUBLICA",
    "INSTITUTO",
    "IDENTIFICACAO",
    "CARTEIRA",
    "IDENTIDADE",
    "JUSTICA",
    "ELEITORAL",
    "TITULO",
    "NASCIMENTO",
    "INSCRICAO",
    "ZONA",
    "SECAO",
    "MUNICIPIO",
    "VALIDADE",
    "EXPEDICAO",
    "REGISTRO",
    "GERAL",
    "CPF",
    "NATURALIDADE",
    "ORGAO",
    "EXPEDIDOR"
}


def limpar_nome(valor):
    valor = str(valor or "")

    valor = re.sub(
        r"[^A-Za-zÀ-ÿ\s]",
        " ",
        valor
    )

    valor = re.sub(
        r"\s+",
        " ",
        valor
    )

    return valor.strip().upper()


def parece_nome(valor):
    valor = limpar_nome(valor)

    if not valor:
        return False

    palavras = valor.split()

    if len(palavras) < 2:
        return False

    if len(valor) < 7:
        return False

    palavras_norm = {
        normalizar_texto(palavra)
        for palavra in palavras
    }

    proibidas = (
        palavras_norm
        & PALAVRAS_PROIBIDAS_NOME
    )

    if len(proibidas) >= 2:
        return False

    return True


# ============================================================
# IDENTIFICAÇÃO DOS DOCUMENTOS
# ============================================================

def identificar_documentos(texto):
    texto_norm = normalizar_texto(texto)

    documentos = []

    sinais_titulo = [
        "TITULO ELEITORAL",
        "JUSTICA ELEITORAL",
        "NOME DO ELEITOR",
        "INSCRICAO",
        "ZONA",
        "SECAO"
    ]

    pontos_titulo = sum(
        sinal in texto_norm
        for sinal in sinais_titulo
    )

    if pontos_titulo >= 2:
        documentos.append(
            "TITULO_ELEITORAL"
        )

    sinais_identidade = [
        "CARTEIRA DE IDENTIDADE",
        "REGISTRO GERAL",
        "INSTITUTO DE IDENTIFICACAO",
        "SECRETARIA DE ESTADO DA SEGURANCA",
        "ORGAO EXPEDIDOR",
        "NATURALIDADE"
    ]

    pontos_identidade = sum(
        sinal in texto_norm
        for sinal in sinais_identidade
    )

    if pontos_identidade >= 2:
        documentos.append(
            "IDENTIDADE"
        )

    sinais_cnh = [
        "CARTEIRA NACIONAL DE HABILITACAO",
        "PERMISSAO PARA DIRIGIR",
        "HABILITACAO",
        "CATEGORIA",
        "ACC"
    ]

    pontos_cnh = sum(
        sinal in texto_norm
        for sinal in sinais_cnh
    )

    if (
        "CARTEIRA NACIONAL DE HABILITACAO"
        in texto_norm
        or pontos_cnh >= 3
    ):
        documentos.append(
            "CNH"
        )

    sinais_endereco = [
        "CEP",
        "ENDERECO",
        "RUA",
        "AVENIDA",
        "TRAVESSA",
        "BAIRRO",
        "FATURA",
        "VENCIMENTO"
    ]

    pontos_endereco = sum(
        sinal in texto_norm
        for sinal in sinais_endereco
    )

    if pontos_endereco >= 3:
        documentos.append(
            "COMPROVANTE_ENDERECO"
        )

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
# CPF
# ============================================================

def extrair_cpf(texto):
    texto = str(texto or "")

    candidatos = re.findall(
        r"(?<!\d)"
        r"(\d{3})[.\s-]?"
        r"(\d{3})[.\s-]?"
        r"(\d{3})[-.\s]?"
        r"(\d{2})"
        r"(?!\d)",
        texto
    )

    for partes in candidatos:
        cpf = "".join(partes)

        if cpf_valido(cpf):
            return formatar_cpf(cpf)

    # Também procura CPF contínuo.
    for candidato in re.findall(
        r"(?<!\d)\d{11}(?!\d)",
        texto
    ):
        if cpf_valido(candidato):
            return formatar_cpf(
                candidato
            )

    return ""


# ============================================================
# DATA DE NASCIMENTO
# ============================================================

def extrair_data_nascimento(texto):
    linhas = linhas_texto(texto)

    padrao_data = (
        r"\b"
        r"(\d{1,2})"
        r"[/.\-]"
        r"(\d{1,2})"
        r"[/.\-]"
        r"(\d{4})"
        r"\b"
    )

    # Prioridade: datas próximas do rótulo.
    for i, linha in enumerate(linhas):

        linha_norm = normalizar_linha(
            linha
        )

        if (
            "NASCIMENTO"
            not in linha_norm
            and "NASC"
            not in linha_norm
            and "BIRTH"
            not in linha_norm
        ):
            continue

        trecho = " ".join(
            linhas[
                i:min(
                    i + 4,
                    len(linhas)
                )
            ]
        )

        for match in re.finditer(
            padrao_data,
            trecho
        ):
            valor = (
                f"{int(match.group(1)):02d}/"
                f"{int(match.group(2)):02d}/"
                f"{match.group(3)}"
            )

            if data_valida(valor):
                return valor

    # Fallback para documentos onde rótulo e valor
    # ficaram separados pelo OCR.
    datas = []

    for match in re.finditer(
        padrao_data,
        texto
    ):
        valor = (
            f"{int(match.group(1)):02d}/"
            f"{int(match.group(2)):02d}/"
            f"{match.group(3)}"
        )

        if not data_valida(valor):
            continue

        ano = int(
            match.group(3)
        )

        if 1900 <= ano <= 2015:
            datas.append(
                valor
            )

    if datas:
        return datas[0]

    return ""


# ============================================================
# TÍTULO ELEITORAL
# ============================================================

def corrigir_numero_ocr(valor):
    valor = str(valor or "").upper()

    mapa = str.maketrans(
        {
            "O": "0",
            "Q": "0",
            "I": "1",
            "L": "1",
            "S": "5",
            "B": "8",
            "Z": "2",
            "G": "6"
        }
    )

    valor = valor.translate(
        mapa
    )

    return somente_numeros(
        valor
    )


def extrair_titulo_zona_secao(texto):
    linhas = linhas_texto(texto)

    titulo = ""
    zona = ""
    secao = ""

    # --------------------------------------------------------
    # PROCURA REGIÃO DO TÍTULO
    # --------------------------------------------------------

    inicio = 0

    for i, linha in enumerate(linhas):

        linha_norm = normalizar_linha(
            linha
        )

        if (
            "TITULO ELEITORAL"
            in linha_norm
            or "JUSTICA ELEITORAL"
            in linha_norm
        ):
            inicio = i

    trecho_titulo = "\n".join(
        linhas[inicio:]
    )

    # --------------------------------------------------------
    # INSCRIÇÃO / TÍTULO
    # --------------------------------------------------------

    for i, linha in enumerate(
        linhas[inicio:],
        start=inicio
    ):

        linha_norm = normalizar_linha(
            linha
        )

        if "INSCRICAO" not in linha_norm:
            continue

        trecho = " ".join(
            linhas[
                i:min(
                    i + 4,
                    len(linhas)
                )
            ]
        )

        candidatos = re.findall(
            r"[0-9OQILSBZG]{10,16}",
            trecho.upper()
        )

        for candidato in candidatos:

            numero = corrigir_numero_ocr(
                candidato
            )

            if len(numero) == 12:
                titulo = numero
                break

        if titulo:
            break

    # Procura qualquer sequência de 12 dígitos
    # somente dentro do bloco eleitoral.
    if not titulo:

        candidatos = re.findall(
            r"(?<!\d)\d{12}(?!\d)",
            trecho_titulo
        )

        if candidatos:
            titulo = candidatos[0]

    # --------------------------------------------------------
    # ZONA
    # --------------------------------------------------------

    match = re.search(
        r"\bZONA\b"
        r"[\s:|;\-]*"
        r"([0-9OQILSBZG]{1,3})",
        trecho_titulo,
        re.I
    )

    if match:

        zona = corrigir_numero_ocr(
            match.group(1)
        )

        if zona:
            zona = zona.zfill(3)

    # --------------------------------------------------------
    # SEÇÃO
    # --------------------------------------------------------

    match = re.search(
        r"\bSE[CÇ][AÃ]O\b"
        r"[\s:|;\-]*"
        r"([0-9OQILSBZG]{1,4})",
        trecho_titulo,
        re.I
    )

    if match:

        secao = corrigir_numero_ocr(
            match.group(1)
        )

        if secao:
            secao = secao.zfill(4)

    # --------------------------------------------------------
    # CASO INSCRIÇÃO / ZONA / SEÇÃO ESTEJAM NA MESMA LINHA
    # --------------------------------------------------------

    if (
        not titulo
        or not zona
        or not secao
    ):

        for linha in linhas[
            inicio:
        ]:

            numeros = re.findall(
                r"(?<!\d)\d{2,12}(?!\d)",
                linha
            )

            titulo_linha = [
                n
                for n in numeros
                if len(n) == 12
            ]

            pequenos = [
                n
                for n in numeros
                if 1 <= len(n) <= 4
            ]

            if (
                titulo_linha
                and len(pequenos) >= 2
            ):

                if not titulo:
                    titulo = (
                        titulo_linha[0]
                    )

                if not zona:
                    zona = (
                        pequenos[-2]
                        .zfill(3)
                    )

                if not secao:
                    secao = (
                        pequenos[-1]
                        .zfill(4)
                    )

                break

    return (
        titulo,
        zona,
        secao
    )


# ============================================================
# NOME DO ELEITOR
# ============================================================

def extrair_nome_titulo(texto):
    linhas = linhas_texto(texto)

    inicio = 0

    for i, linha in enumerate(linhas):

        linha_norm = normalizar_linha(
            linha
        )

        if (
            "TITULO ELEITORAL"
            in linha_norm
            or "JUSTICA ELEITORAL"
            in linha_norm
        ):
            inicio = i

    for i in range(
        inicio,
        len(linhas)
    ):

        linha = linhas[i]

        linha_norm = normalizar_linha(
            linha
        )

        if (
            "NOME DO ELEITOR"
            not in linha_norm
        ):
            continue

        # Nome pode estar na própria linha.
        resto = re.sub(
            r"(?i).*NOME\s+DO\s+ELEITOR",
            "",
            linha
        )

        resto = limpar_nome(
            resto
        )

        if parece_nome(resto):
            return resto

        # Ou nas linhas seguintes.
        for j in range(
            i + 1,
            min(
                i + 5,
                len(linhas)
            )
        ):

            candidato = limpar_nome(
                linhas[j]
            )

            if parece_nome(
                candidato
            ):
                return candidato

    return ""


# ============================================================
# NOME DA IDENTIDADE
# ============================================================

def extrair_nome_identidade(texto):
    linhas = linhas_texto(texto)

    for i, linha in enumerate(
        linhas
    ):

        linha_norm = normalizar_linha(
            linha
        )

        # Evita NOME DO ELEITOR.
        if "NOME DO ELEITOR" in linha_norm:
            continue

        if not (
            linha_norm == "NOME"
            or linha_norm.startswith(
                "NOME "
            )
        ):
            continue

        resto = re.sub(
            r"(?i)^\s*NOME\s*[:|\-]*",
            "",
            linha
        )

        resto = limpar_nome(
            resto
        )

        if parece_nome(resto):
            return resto

        for j in range(
            i + 1,
            min(
                i + 4,
                len(linhas)
            )
        ):

            candidato = limpar_nome(
                linhas[j]
            )

            if parece_nome(
                candidato
            ):
                return candidato

    return ""


# ============================================================
# NOME PRINCIPAL
# ============================================================

def extrair_nome(texto):
    documentos = identificar_documentos(
        texto
    )

    # Título eleitoral tem prioridade porque o campo
    # "NOME DO ELEITOR" costuma ser explícito.
    if (
        "TITULO_ELEITORAL"
        in documentos
    ):

        nome = extrair_nome_titulo(
            texto
        )

        if nome:
            return nome

    nome = extrair_nome_identidade(
        texto
    )

    if nome:
        return nome

    return ""


# ============================================================
# RG
# ============================================================

def extrair_rg(texto):
    padroes = [
        (
            r"REGISTRO\s+GERAL"
            r"[\s:|\-]*"
            r"([0-9.\-]{4,20})"
        ),
        (
            r"\bRG\b"
            r"[\s:|\-]*"
            r"([0-9.\-]{4,20})"
        )
    ]

    for padrao in padroes:

        match = re.search(
            padrao,
            texto,
            re.I
        )

        if not match:
            continue

        numero = somente_numeros(
            match.group(1)
        )

        if 4 <= len(numero) <= 14:
            return numero

    return ""


# ============================================================
# NOME DA MÃE
# ============================================================

def extrair_nome_mae(
    texto,
    nome_pessoa=""
):
    linhas = linhas_texto(texto)

    nome_pessoa_norm = normalizar_texto(
        nome_pessoa
    )

    # --------------------------------------------------------
    # RÓTULO EXPLÍCITO
    # --------------------------------------------------------

    for i, linha in enumerate(
        linhas
    ):

        linha_norm = normalizar_linha(
            linha
        )

        if not (
            "NOME DA MAE"
            in linha_norm
            or linha_norm == "MAE"
        ):
            continue

        resto = re.sub(
            r"(?i).*"
            r"(?:NOME\s+DA\s+M[AÃ]E|M[AÃ]E)"
            r"\s*[:|\-]*",
            "",
            linha
        )

        resto = limpar_nome(
            resto
        )

        if parece_nome(resto):
            return resto

        for j in range(
            i + 1,
            min(
                i + 4,
                len(linhas)
            )
        ):

            candidato = limpar_nome(
                linhas[j]
            )

            if (
                parece_nome(candidato)
                and normalizar_texto(
                    candidato
                ) != nome_pessoa_norm
            ):
                return candidato

    # --------------------------------------------------------
    # FILIAÇÃO
    # --------------------------------------------------------

    for i, linha in enumerate(
        linhas
    ):

        if (
            "FILIACAO"
            not in normalizar_linha(
                linha
            )
        ):
            continue

        candidatos = []

        for j in range(
            i + 1,
            min(
                i + 8,
                len(linhas)
            )
        ):

            candidato = limpar_nome(
                linhas[j]
            )

            if not parece_nome(
                candidato
            ):
                continue

            if (
                normalizar_texto(
                    candidato
                )
                == nome_pessoa_norm
            ):
                continue

            candidatos.append(
                candidato
            )

        # Em RGs tradicionais:
        # primeiro costuma ser pai,
        # segundo costuma ser mãe.
        if len(candidatos) >= 2:
            return candidatos[1]

        if len(candidatos) == 1:
            return candidatos[0]

    # --------------------------------------------------------
    # RG ANTIGO: FILIAÇÃO PODE PERDER O RÓTULO NO OCR
    # --------------------------------------------------------

    indice_naturalidade = None

    for i, linha in enumerate(
        linhas
    ):

        if (
            "NATURALIDADE"
            in normalizar_linha(
                linha
            )
        ):
            indice_naturalidade = i
            break

    if indice_naturalidade is not None:

        candidatos = []

        for j in range(
            max(
                0,
                indice_naturalidade - 8
            ),
            indice_naturalidade
        ):

            candidato = limpar_nome(
                linhas[j]
            )

            if not parece_nome(
                candidato
            ):
                continue

            candidato_norm = (
                normalizar_texto(
                    candidato
                )
            )

            if (
                candidato_norm
                == nome_pessoa_norm
            ):
                continue

            candidatos.append(
                candidato
            )

        if len(candidatos) >= 2:
            return candidatos[-1]

    return ""


# ============================================================
# CIDADE
# ============================================================

def extrair_cidade(texto):
    linhas = linhas_texto(texto)

    # Título eleitoral.
    for i, linha in enumerate(
        linhas
    ):

        linha_norm = normalizar_linha(
            linha
        )

        if (
            "MUNICIPIO"
            not in linha_norm
        ):
            continue

        trecho = " ".join(
            linhas[
                i:min(
                    i + 4,
                    len(linhas)
                )
            ]
        )

        match = re.search(
            r"([A-ZÀ-Ÿ][A-ZÀ-Ÿ\s]{2,40})"
            r"\s*/\s*"
            r"([A-Z]{2})",
            trecho,
            re.I
        )

        if match:

            cidade = limpar_nome(
                match.group(1)
            )

            cidade_norm = (
                normalizar_texto(
                    cidade
                )
            )

            cidade_norm = re.sub(
                r"^MUNICIPIO\s+UF\s*",
                "",
                cidade_norm
            )

            cidade_norm = re.sub(
                r"^MUNICIPIO\s*",
                "",
                cidade_norm
            )

            if cidade_norm:
                return cidade_norm

    return ""


# ============================================================
# TELEFONE
# ============================================================

def extrair_telefone(texto):
    padroes = [
        (
            r"(?:\+?55\s*)?"
            r"\(?(\d{2})\)?"
            r"[\s.\-]*"
            r"(9\d{4})"
            r"[\s.\-]*"
            r"(\d{4})"
        ),
        (
            r"(?:\+?55\s*)?"
            r"\(?(\d{2})\)?"
            r"[\s.\-]*"
            r"(\d{4})"
            r"[\s.\-]*"
            r"(\d{4})"
        )
    ]

    for padrao in padroes:

        match = re.search(
            padrao,
            str(texto or "")
        )

        if not match:
            continue

        ddd = match.group(1)
        parte1 = match.group(2)
        parte2 = match.group(3)

        return (
            f"({ddd}) "
            f"{parte1}-{parte2}"
        )

    return ""


# ============================================================
# ENDEREÇO
# ============================================================

def extrair_endereco(texto):
    linhas = linhas_texto(texto)

    resultado = {
        "endereco": "",
        "numero": "",
        "bairro": "",
        "cidade": ""
    }

    tipos = (
        r"(?:"
        r"RUA|R\.|"
        r"AVENIDA|AV\.|"
        r"TRAVESSA|TRAV\.|"
        r"RODOVIA|ROD\.|"
        r"ESTRADA|EST\.|"
        r"PRACA|PRAÇA|"
        r"ALAMEDA|"
        r"LOTEAMENTO|"
        r"CONJUNTO"
        r")"
    )

    for linha in linhas:

        linha_norm = normalizar_linha(
            linha
        )

        if not re.search(
            rf"\b{tipos}\b",
            linha_norm,
            re.I
        ):
            continue

        # Evita cabeçalhos institucionais.
        if any(
            palavra in linha_norm
            for palavra in [
                "REPUBLICA",
                "SECRETARIA",
                "JUSTICA ELEITORAL"
            ]
        ):
            continue

        linha_limpa = re.sub(
            r"\s+",
            " ",
            linha
        ).strip()

        match_numero = re.search(
            r"(?:,\s*|\bN[º°O]?\s*)"
            r"(\d+[A-Z]?)\b",
            linha_limpa,
            re.I
        )

        if match_numero:

            resultado["numero"] = (
                match_numero.group(1)
                .upper()
            )

            resultado["endereco"] = (
                linha_limpa[
                    :match_numero.start()
                ]
                .strip(" ,;-")
                .upper()
            )

            resto = (
                linha_limpa[
                    match_numero.end():
                ]
                .strip(" ,;-")
            )

            if resto:

                resto = re.split(
                    r"\bCEP\b",
                    resto,
                    flags=re.I
                )[0]

                resultado["bairro"] = (
                    resto
                    .strip(" ,;-")
                    .upper()
                )

        else:

            resultado["endereco"] = (
                linha_limpa.upper()
            )

        break

    return resultado


# ============================================================
# SEPARAÇÃO APROXIMADA DOS DOCUMENTOS
# ============================================================

def separar_blocos_documentos(texto):
    linhas = linhas_texto(texto)

    blocos = {
        "TITULO_ELEITORAL": [],
        "IDENTIDADE": [],
        "CNH": [],
        "COMPROVANTE_ENDERECO": [],
        "OUTROS": []
    }

    bloco_atual = "OUTROS"

    for linha in linhas:

        linha_norm = normalizar_linha(
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
            valor
        ).strip()
        for chave, valor
        in blocos.items()
        if valor
    }


# ============================================================
# EXTRAÇÃO PRINCIPAL
# ============================================================

def extrair_campos(texto):
    """
    Extrai os campos usando o tipo de documento
    e os rótulos encontrados pelo OCR.
    """

    dados = resultado_vazio()

    documentos = (
        identificar_documentos(
            texto
        )
    )

    dados["nome"] = (
        extrair_nome(
            texto
        )
    )

    dados["cpf"] = (
        extrair_cpf(
            texto
        )
    )

    dados["data_nascimento"] = (
        extrair_data_nascimento(
            texto
        )
    )

    dados["rg"] = (
        extrair_rg(
            texto
        )
    )

    dados["nome_mae"] = (
        extrair_nome_mae(
            texto,
            dados["nome"]
        )
    )

    if (
        "TITULO_ELEITORAL"
        in documentos
    ):

        (
            titulo,
            zona,
            secao
        ) = extrair_titulo_zona_secao(
            texto
        )

        dados["titulo"] = titulo
        dados["zona"] = zona
        dados["secao"] = secao

        dados["cidade"] = (
            extrair_cidade(
                texto
            )
        )

    dados["telefone"] = (
        extrair_telefone(
            texto
        )
    )

    endereco = (
        extrair_endereco(
            texto
        )
    )

    dados["endereco"] = (
        endereco["endereco"]
    )

    dados["numero"] = (
        endereco["numero"]
    )

    dados["bairro"] = (
        endereco["bairro"]
    )

    if (
        not dados["cidade"]
        and endereco["cidade"]
    ):
        dados["cidade"] = (
            endereco["cidade"]
        )

    return dados


# ============================================================
# FUNÇÃO PRINCIPAL DO MÓDULO
# ============================================================

def analisar_documentos(texto):
    documentos = (
        identificar_documentos(
            texto
        )
    )

    blocos = (
        separar_blocos_documentos(
            texto
        )
    )

    dados = extrair_campos(
        texto
    )

    return {
        "documentos":
            documentos,

        "blocos":
            blocos,

        "dados":
            dados
    }

# No início do app.py, importe a função
from extrator_documentos import extrair_dados_completos_prioritario

# E no processamento do lote, quando o nome estiver errado:
nome_errado = dados.get("nome") in ["WILLAKS FÍRÂELRA DA SILVA", "WILLAKS FIRAELRA DA SILVA", ""]
if nome_errado or not parece_nome(dados.get("nome")):
    try:
        arquivo.seek(0)
        imagem_fallback = Image.open(arquivo).convert("RGB")
        texto_tesseract_fallback = executar_tesseract_imagem(imagem_fallback)
        
        if texto_tesseract_fallback:
            # Usa a nova função prioritária
            dados_extraidos = extrair_dados_completos_prioritario(texto_tesseract_fallback)
            
            if dados_extraidos.get("nome") and dados_extraidos["nome"] not in ["WILLAKS FÍRÂELRA DA SILVA", "WILLAKS FIRAELRA DA SILVA", ""]:
                dados["nome"] = dados_extraidos["nome"]
                texto = texto_tesseract_fallback
            
            for campo in ["cpf", "titulo", "data_nascimento", "nome_mae", "zona", "secao", "rg"]:
                if dados_extraidos.get(campo) and not dados.get(campo):
                    dados[campo] = dados_extraidos[campo]
        
        del imagem_fallback
        gc.collect()
    except Exception:
        pass
