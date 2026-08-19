import re
import unicodedata
from datetime import datetime


# ============================================================
# ESTRUTURA PADRÃO
# ============================================================

CAMPOS = [
    "nome",
    "cpf",
    "rg",
    "data_nascimento",
    "nome_mae",
    "titulo",
    "zona",
    "secao",
    "endereco",
    "numero",
    "bairro",
    "cidade",
    "telefone",
    "nis",
    "dap",
    "sus",
]


def resultado_vazio():
    return {
        campo: ""
        for campo in CAMPOS
    }


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def remover_acentos(texto):
    texto = str(texto or "")

    return "".join(
        c
        for c in unicodedata.normalize(
            "NFD",
            texto
        )
        if unicodedata.category(c) != "Mn"
    )


def normalizar_texto(texto):
    texto = remover_acentos(
        texto
    ).upper()

    texto = re.sub(
        r"[ \t]+",
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


def obter_linhas(texto):
    return [
        linha.strip()
        for linha in str(
            texto or ""
        ).splitlines()
        if linha.strip()
    ]


def limpar_nome(valor):
    valor = str(
        valor or ""
    )

    valor = re.sub(
        r"[^A-Za-zÀ-ÿ'\s]",
        " ",
        valor
    )

    valor = re.sub(
        r"\s+",
        " ",
        valor
    )

    return valor.strip().upper()


# ============================================================
# UTILIDADES DE CONTEXTO
# ============================================================

def contexto_linhas(
    linhas,
    indice,
    antes=1,
    depois=3
):
    inicio = max(
        0,
        indice - antes
    )

    fim = min(
        len(linhas),
        indice + depois + 1
    )

    return "\n".join(
        linhas[inicio:fim]
    )


def contem_algum(
    texto,
    termos
):
    texto = normalizar_texto(
        texto
    )

    return any(
        normalizar_texto(termo)
        in texto
        for termo in termos
    )


# ============================================================
# CPF
# ============================================================

def cpf_valido(cpf):
    cpf = somente_numeros(
        cpf
    )

    if len(cpf) != 11:
        return False

    if cpf == cpf[0] * 11:
        return False

    try:
        soma = sum(
            int(cpf[i])
            * (10 - i)
            for i in range(9)
        )

        d1 = (
            11 - soma % 11
        )

        if d1 >= 10:
            d1 = 0

        if d1 != int(
            cpf[9]
        ):
            return False

        soma = sum(
            int(cpf[i])
            * (11 - i)
            for i in range(10)
        )

        d2 = (
            11 - soma % 11
        )

        if d2 >= 10:
            d2 = 0

        return (
            d2
            == int(cpf[10])
        )

    except Exception:
        return False


def formatar_cpf(cpf):
    cpf = somente_numeros(
        cpf
    )

    if len(cpf) != 11:
        return cpf

    return (
        f"{cpf[:3]}."
        f"{cpf[3:6]}."
        f"{cpf[6:9]}-"
        f"{cpf[9:]}"
    )


def extrair_cpf(texto):
    """
    Procura CPF em TODO o conteúdo.

    Não depende do tipo de documento.
    """

    texto = str(
        texto or ""
    )

    candidatos = []

    # CPF formatado ou parcialmente formatado.
    padrao = re.compile(
        r"(?<!\d)"
        r"(\d{3})"
        r"[\.\s\-]?"
        r"(\d{3})"
        r"[\.\s\-]?"
        r"(\d{3})"
        r"[\.\s\-]?"
        r"(\d{2})"
        r"(?!\d)"
    )

    for match in padrao.finditer(
        texto
    ):
        numero = "".join(
            match.groups()
        )

        candidatos.append(
            numero
        )

    # Também procura CPF dentro de linhas maiores,
    # como acontece na CIN/MRZ.
    for numero in re.findall(
        r"\d{11}",
        texto
    ):
        candidatos.append(
            numero
        )

    vistos = set()

    for numero in candidatos:

        numero = somente_numeros(
            numero
        )

        if numero in vistos:
            continue

        vistos.add(
            numero
        )

        if cpf_valido(
            numero
        ):
            return formatar_cpf(
                numero
            )

    return ""


# ============================================================
# DATAS
# ============================================================

def data_valida(data):
    try:
        datetime.strptime(
            data,
            "%d/%m/%Y"
        )

        return True

    except Exception:
        return False


def extrair_datas(texto):
    resultados = []

    padrao = re.compile(
        r"\b"
        r"(\d{1,2})"
        r"[/.\-]"
        r"(\d{1,2})"
        r"[/.\-]"
        r"(\d{4})"
        r"\b"
    )

    for match in padrao.finditer(
        str(texto or "")
    ):
        data = (
            f"{int(match.group(1)):02d}/"
            f"{int(match.group(2)):02d}/"
            f"{match.group(3)}"
        )

        if data_valida(
            data
        ):
            resultados.append(
                data
            )

    return resultados


def extrair_data_nascimento(texto):
    linhas = obter_linhas(
        texto
    )

    # Primeiro procura data associada
    # explicitamente a nascimento.
    for i, linha in enumerate(
        linhas
    ):
        if not contem_algum(
            linha,
            [
                "NASCIMENTO",
                "DATA NASC",
                "DATE OF BIRTH",
                "NASC."
            ]
        ):
            continue

        bloco = contexto_linhas(
            linhas,
            i,
            antes=0,
            depois=3
        )

        datas = extrair_datas(
            bloco
        )

        if datas:
            return datas[0]

    # Fallback:
    # entre todas as datas, prioriza anos
    # compatíveis com nascimento.
    datas = extrair_datas(
        texto
    )

    candidatos = []

    for data in datas:
        try:
            ano = int(
                data[-4:]
            )

            if 1900 <= ano <= 2020:
                candidatos.append(
                    data
                )

        except Exception:
            pass

    return (
        candidatos[0]
        if candidatos
        else ""
    )


# ============================================================
# NOME
# ============================================================

ROTULOS_INVALIDOS_NOME = [
    "REPUBLICA",
    "FEDERATIVA",
    "BRASIL",
    "ESTADO",
    "SECRETARIA",
    "SEGURANCA",
    "PUBLICA",
    "PERICIA",
    "OFICIAL",
    "INSTITUTO",
    "IDENTIFICACAO",
    "JUSTICA",
    "ELEITORAL",
    "TITULO",
    "CARTEIRA",
    "IDENTIDADE",
    "REGISTRO GERAL",
    "REGISTRO CIVIL",
    "NASCIMENTO",
    "NATURALIDADE",
    "MUNICIPIO",
    "INSCRICAO",
    "ZONA",
    "SECAO",
    "CPF",
    "FILIACAO",
    "ORGAO EXPEDIDOR",
    "DATA DE EMISSAO",
    "DATA DE EXPEDICAO",
    "VALIDADE",
    "POLEGAR",
    "ASSINATURA",
]


def parece_nome(valor):
    nome = limpar_nome(
        valor
    )

    if len(nome) < 7:
        return False

    palavras = nome.split()

    if len(palavras) < 2:
        return False

    normalizado = normalizar_texto(
        nome
    )

    if any(
        termo in normalizado
        for termo
        in ROTULOS_INVALIDOS_NOME
    ):
        return False

    # Evita lixo OCR muito curto.
    palavras_validas = [
        palavra
        for palavra in palavras
        if len(palavra) >= 2
    ]

    return (
        len(palavras_validas)
        >= 2
    )


def candidato_depois_rotulo(
    linhas,
    indice,
    rotulos,
    limite=4
):
    linha = linhas[
        indice
    ]

    linha_norm = normalizar_texto(
        linha
    )

    # Tenta retirar o rótulo da própria linha.
    for rotulo in rotulos:
        rotulo_norm = (
            normalizar_texto(
                rotulo
            )
        )

        pos = linha_norm.find(
            rotulo_norm
        )

        if pos >= 0:
            # Usamos regex no original para preservar acentos.
            partes = re.split(
                re.escape(rotulo),
                linha,
                maxsplit=1,
                flags=re.I
            )

            if len(partes) == 2:
                candidato = limpar_nome(
                    partes[1]
                )

                if parece_nome(
                    candidato
                ):
                    return candidato

    # Depois procura linhas seguintes.
    for j in range(
        indice + 1,
        min(
            indice + limite + 1,
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


def extrair_nome(texto):
    """
    Procura nome independentemente
    do documento de origem.
    """

    linhas = obter_linhas(
        texto
    )

    prioridades = [
        [
            "NOME DO ELEITOR"
        ],
        [
            "NOME / NAME"
        ],
        [
            "NOME"
        ],
        [
            "REGISTRO CIVIL"
        ],
    ]

    for rotulos in prioridades:

        for i, linha in enumerate(
            linhas
        ):
            if not contem_algum(
                linha,
                rotulos
            ):
                continue

            # NOME DO ELEITOR tem tratamento direto.
            if (
                "NOME DO ELEITOR"
                in normalizar_texto(
                    linha
                )
            ):
                resto = re.sub(
                    r"(?i).*NOME\s+DO\s+ELEITOR",
                    "",
                    linha
                )

                candidato = limpar_nome(
                    resto
                )

                if parece_nome(
                    candidato
                ):
                    return candidato

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

            # REGISTRO CIVIL pode trazer
            # o nome na mesma linha.
            if (
                "REGISTRO CIVIL"
                in normalizar_texto(
                    linha
                )
            ):
                resto = re.sub(
                    r"(?i).*REGISTRO\s+CIVIL",
                    "",
                    linha
                )

                candidato = limpar_nome(
                    resto
                )

                if parece_nome(
                    candidato
                ):
                    return candidato

            # NOME genérico.
            if (
                normalizar_texto(
                    linha
                ).startswith("NOME")
            ):
                resto = re.sub(
                    r"(?i)^.*?\bNOME\b"
                    r"(?:\s*/\s*NAME)?"
                    r"\s*[:\-]*",
                    "",
                    linha
                )

                candidato = limpar_nome(
                    resto
                )

                if parece_nome(
                    candidato
                ):
                    return candidato

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
# FILIAÇÃO / MÃE
# ============================================================

def extrair_nome_mae(
    texto,
    nome_pessoa=""
):
    linhas = obter_linhas(
        texto
    )

    nome_pessoa_norm = (
        normalizar_texto(
            nome_pessoa
        )
    )

    # --------------------------------------------------------
    # Rótulo explícito MÃE
    # --------------------------------------------------------

    for i, linha in enumerate(
        linhas
    ):
        linha_norm = normalizar_texto(
            linha
        )

        if not (
            "NOME DA MAE"
            in linha_norm
            or re.search(
                r"\bMAE\b",
                linha_norm
            )
        ):
            continue

        resto = re.sub(
            r"(?i).*"
            r"(?:NOME\s+DA\s+M[AÃ]E|M[AÃ]E)"
            r"\s*[:\-]*",
            "",
            linha
        )

        candidato = limpar_nome(
            resto
        )

        if parece_nome(
            candidato
        ):
            return candidato

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
        if "FILIACAO" not in (
            normalizar_texto(
                linha
            )
        ):
            continue

        nomes = []

        # Pode haver nome na própria linha
        # depois do rótulo.
        resto = re.sub(
            r"(?i).*FILI[AÇC][AÃA]O",
            "",
            linha
        )

        partes = re.split(
            r"\s{2,}|[|;]",
            resto
        )

        for parte in partes:
            candidato = limpar_nome(
                parte
            )

            if (
                parece_nome(candidato)
                and normalizar_texto(
                    candidato
                ) != nome_pessoa_norm
            ):
                nomes.append(
                    candidato
                )

        # E nas linhas seguintes.
        for j in range(
            i + 1,
            min(
                i + 8,
                len(linhas)
            )
        ):
            linha_j = linhas[j]

            linha_j_norm = (
                normalizar_texto(
                    linha_j
                )
            )

            if contem_algum(
                linha_j_norm,
                [
                    "DATA NASCIMENTO",
                    "NASCIMENTO",
                    "NATURALIDADE",
                    "ORGAO EXPEDIDOR",
                    "REGISTRO GERAL",
                    "CPF",
                    "ASSINATURA"
                ]
            ):
                break

            candidato = limpar_nome(
                linha_j
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

            if candidato not in nomes:
                nomes.append(
                    candidato
                )

        # Em filiação brasileira tradicional:
        # pai primeiro, mãe depois.
        if len(nomes) >= 2:
            return nomes[1]

        # Se o OCR conseguiu identificar somente
        # um nome após FILIAÇÃO, não vamos inventar
        # que seja a mãe.
        return ""

    return ""


# ============================================================
# RG
# ============================================================

def extrair_rg(texto):
    linhas = obter_linhas(
        texto
    )

    rotulos = [
        "REGISTRO GERAL",
        "RG"
    ]

    for i, linha in enumerate(
        linhas
    ):
        linha_norm = normalizar_texto(
            linha
        )

        if not any(
            (
                rotulo == "RG"
                and re.search(
                    r"\bRG\b",
                    linha_norm
                )
            )
            or (
                rotulo != "RG"
                and rotulo
                in linha_norm
            )
            for rotulo in rotulos
        ):
            continue

        bloco = contexto_linhas(
            linhas,
            i,
            antes=0,
            depois=1
        )

        # Retira datas para evitar pegar
        # data de expedição.
        bloco = re.sub(
            r"\b\d{1,2}"
            r"[/.\-]"
            r"\d{1,2}"
            r"[/.\-]"
            r"\d{4}\b",
            " ",
            bloco
        )

        # Prioridade para número imediatamente
        # após REGISTRO GERAL.
        match = re.search(
            r"(?i)"
            r"REGISTRO\s+GERAL"
            r"[^0-9]{0,10}"
            r"(\d[\d.\-\s]{4,14})",
            bloco
        )

        if match:
            numero = somente_numeros(
                match.group(1)
            )

            if 5 <= len(numero) <= 12:
                return numero

        candidatos = re.findall(
            r"(?<!\d)"
            r"\d{5,12}"
            r"(?!\d)",
            bloco
        )

        for numero in candidatos:
            if len(numero) == 11:
                # Pode ser CPF.
                if cpf_valido(
                    numero
                ):
                    continue

            return numero

    return ""


# ============================================================
# TÍTULO / ZONA / SEÇÃO
# ============================================================

def pontuar_titulo(
    texto,
    inicio,
    fim
):
    """
    Pontua candidato de 12 dígitos
    pelo contexto ao redor.
    """

    contexto = normalizar_texto(
        texto[
            max(
                0,
                inicio - 100
            ):
            min(
                len(texto),
                fim + 100
            )
        ]
    )

    pontos = 0

    for termo, peso in [
        ("INSCRICAO", 5),
        ("TITULO ELEITORAL", 5),
        ("JUSTICA ELEITORAL", 4),
        ("ZONA", 3),
        ("SECAO", 3),
        ("ELEITOR", 2),
    ]:
        if termo in contexto:
            pontos += peso

    return pontos


def extrair_titulo(texto):
    texto = str(
        texto or ""
    )

    candidatos = []

    for match in re.finditer(
        r"(?<!\d)"
        r"\d{12}"
        r"(?!\d)",
        texto
    ):
        numero = match.group()

        # CPF de 11 dígitos não interfere aqui.
        pontos = pontuar_titulo(
            texto,
            match.start(),
            match.end()
        )

        candidatos.append(
            (
                pontos,
                numero
            )
        )

    if not candidatos:
        return ""

    candidatos.sort(
        key=lambda item: item[0],
        reverse=True
    )

    melhor_pontos, melhor = (
        candidatos[0]
    )

    # Não aceita 12 dígitos aleatórios
    # sem qualquer contexto eleitoral.
    if melhor_pontos < 3:
        return ""

    return melhor


def extrair_zona_secao(
    texto,
    titulo=""
):
    linhas = obter_linhas(
        texto
    )

    zona = ""
    secao = ""

    # --------------------------------------------------------
    # Busca rótulos diretamente.
    # --------------------------------------------------------

    for i, linha in enumerate(
        linhas
    ):
        linha_norm = normalizar_texto(
            linha
        )

        if "ZONA" in linha_norm:

            bloco = contexto_linhas(
                linhas,
                i,
                antes=0,
                depois=2
            )

            match = re.search(
                r"(?i)\bZONA\b"
                r"[^0-9]{0,15}"
                r"(\d{1,3})",
                bloco
            )

            if match:
                zona = (
                    match.group(1)
                    .zfill(3)
                )

        if "SECAO" in linha_norm:

            bloco = contexto_linhas(
                linhas,
                i,
                antes=0,
                depois=2
            )

            match = re.search(
                r"(?i)"
                r"SE[CÇ][AÃ]O"
                r"[^0-9]{0,15}"
                r"(\d{1,4})",
                bloco
            )

            if match:
                secao = (
                    match.group(1)
                    .zfill(4)
                )

    # --------------------------------------------------------
    # Se temos o título, procuramos números próximos dele.
    #
    # Exemplo:
    # 049028331724 | 022 | 0434
    # --------------------------------------------------------

    if titulo and (
        not zona
        or not secao
    ):
        pos = str(texto).find(
            titulo
        )

        if pos >= 0:
            trecho = str(texto)[
                max(
                    0,
                    pos - 100
                ):
                min(
                    len(str(texto)),
                    pos + len(titulo) + 150
                )
            ]

            pos_local = trecho.find(
                titulo
            )

            depois = trecho[
                pos_local
                + len(titulo):
            ]

            numeros = re.findall(
                r"(?<!\d)"
                r"\d{1,4}"
                r"(?!\d)",
                depois
            )

            candidatos = []

            for numero in numeros:
                valor = int(
                    numero
                )

                # Zona e seção são números pequenos.
                if 0 < valor <= 9999:
                    candidatos.append(
                        numero
                    )

            if len(candidatos) >= 2:

                if not zona:
                    zona = (
                        candidatos[0]
                        .zfill(3)
                    )

                if not secao:
                    secao = (
                        candidatos[1]
                        .zfill(4)
                    )

    return zona, secao


# ============================================================
# CIDADE
# ============================================================

def limpar_cidade(valor):
    cidade = limpar_nome(
        valor
    )

    cidade = re.sub(
        r"(?i)^.*?\bMUNICIPIO\b"
        r"(?:\s*/?\s*UF)?"
        r"\s*",
        "",
        cidade
    )

    cidade = re.sub(
        r"(?i)^.*?\bNATURALIDADE\b"
        r"\s*",
        "",
        cidade
    )

    cidade = re.sub(
        r"^[RLI|]+\s+",
        "",
        cidade
    )

    return cidade.strip()


def extrair_cidade(texto):
    linhas = obter_linhas(
        texto
    )

    # --------------------------------------------------------
    # MUNICÍPIO / UF
    # --------------------------------------------------------

    for i, linha in enumerate(
        linhas
    ):
        if "MUNICIPIO" not in (
            normalizar_texto(
                linha
            )
        ):
            continue

        bloco = contexto_linhas(
            linhas,
            i,
            antes=0,
            depois=3
        )

        # Prioridade para CIDADE / UF.
        matches = re.findall(
            r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s]{2,40}?)"
            r"\s*/\s*"
            r"([A-Z]{2})\b",
            bloco,
            re.I
        )

        for cidade, uf in matches:

            cidade = limpar_cidade(
                cidade
            )

            if (
                cidade
                and "MUNICIPIO"
                not in normalizar_texto(
                    cidade
                )
            ):
                return cidade

    # --------------------------------------------------------
    # NATURALIDADE
    # --------------------------------------------------------

    for i, linha in enumerate(
        linhas
    ):
        if "NATURALIDADE" not in (
            normalizar_texto(
                linha
            )
        ):
            continue

        bloco = contexto_linhas(
            linhas,
            i,
            antes=0,
            depois=2
        )

        match = re.search(
            r"(?i)"
            r"NATURALIDADE"
            r"[^A-Za-zÀ-ÿ]{0,10}"
            r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s]{2,35}?)"
            r"\s*[-/]\s*"
            r"([A-Z]{2})\b",
            bloco
        )

        if match:

            cidade = limpar_cidade(
                match.group(1)
            )

            if cidade:
                return cidade

    return ""


# ============================================================
# TELEFONE
# ============================================================

def extrair_telefone(texto):
    """
    Não aceita qualquer sequência de 10/11
    dígitos como telefone.

    Isso evita transformar CPF, título, RG,
    MRZ etc. em telefone.
    """

    texto = str(
        texto or ""
    )

    # --------------------------------------------------------
    # Mais confiável: (82) 99999-9999
    # --------------------------------------------------------

    padrao = re.compile(
        r"\("
        r"(\d{2})"
        r"\)"
        r"\s*"
        r"(\d{4,5})"
        r"[\s.\-]*"
        r"(\d{4})"
    )

    for match in padrao.finditer(
        texto
    ):
        ddd = match.group(1)
        p1 = match.group(2)
        p2 = match.group(3)

        numero = (
            ddd
            + p1
            + p2
        )

        if len(numero) not in (
            10,
            11
        ):
            continue

        return (
            f"({ddd}) "
            f"{p1}-{p2}"
        )

    # --------------------------------------------------------
    # Sem parênteses:
    # só aceita perto de TELEFONE/CELULAR/FONE/WHATSAPP.
    # --------------------------------------------------------

    linhas = obter_linhas(
        texto
    )

    for i, linha in enumerate(
        linhas
    ):
        if not contem_algum(
            linha,
            [
                "TELEFONE",
                "CELULAR",
                "FONE",
                "WHATSAPP"
            ]
        ):
            continue

        bloco = contexto_linhas(
            linhas,
            i,
            antes=0,
            depois=2
        )

        match = re.search(
            r"(?<!\d)"
            r"(?:55\s*)?"
            r"(\d{2})"
            r"[\s.\-]*"
            r"(9?\d{4})"
            r"[\s.\-]*"
            r"(\d{4})"
            r"(?!\d)",
            bloco
        )

        if match:
            ddd = match.group(1)
            p1 = match.group(2)
            p2 = match.group(3)

            return (
                f"({ddd}) "
                f"{p1}-{p2}"
            )

    return ""


# ============================================================
# ENDEREÇO
# ============================================================

def extrair_endereco(texto):
    dados = {
        "endereco": "",
        "numero": "",
        "bairro": ""
    }

    linhas = obter_linhas(
        texto
    )

    padrao_logradouro = re.compile(
        r"\b("
        r"RUA|"
        r"AVENIDA|"
        r"AV\.?|"
        r"TRAVESSA|"
        r"TRAV\.?|"
        r"RODOVIA|"
        r"ROD\.?|"
        r"ESTRADA|"
        r"PRACA|"
        r"PRAÇA|"
        r"ALAMEDA|"
        r"LOTEAMENTO|"
        r"CONJUNTO"
        r")\b",
        re.I
    )

    for i, linha in enumerate(
        linhas
    ):
        if not padrao_logradouro.search(
            linha
        ):
            continue

        linha_limpa = re.sub(
            r"\s+",
            " ",
            linha
        ).strip()

        # Evita textos institucionais.
        if contem_algum(
            linha_limpa,
            [
                "SECRETARIA",
                "JUSTICA ELEITORAL",
                "REPUBLICA FEDERATIVA"
            ]
        ):
            continue

        match_numero = re.search(
            r"(?:,\s*|\bN[º°O]?\s*)"
            r"(\d+[A-Z]?)\b",
            linha_limpa,
            re.I
        )

        if match_numero:

            dados["endereco"] = (
                linha_limpa[
                    :match_numero.start()
                ]
                .strip(" ,-;")
                .upper()
            )

            dados["numero"] = (
                match_numero.group(1)
                .upper()
            )

            resto = (
                linha_limpa[
                    match_numero.end():
                ]
                .strip(" ,-;")
            )

            resto = re.split(
                r"\bCEP\b",
                resto,
                maxsplit=1,
                flags=re.I
            )[0]

            if resto:
                dados["bairro"] = (
                    resto.upper()
                )

        else:
            dados["endereco"] = (
                linha_limpa.upper()
            )

        return dados

    # Procura campo ENDEREÇO explícito.
    for i, linha in enumerate(
        linhas
    ):
        if "ENDERECO" not in (
            normalizar_texto(
                linha
            )
        ):
            continue

        resto = re.sub(
            r"(?i).*ENDERE[CÇ]O"
            r"\s*[:\-]*",
            "",
            linha
        ).strip()

        if resto:
            dados["endereco"] = (
                resto.upper()
            )

        elif i + 1 < len(linhas):
            dados["endereco"] = (
                linhas[i + 1]
                .upper()
            )

        break

    return dados


# ============================================================
# NIS
# ============================================================

def extrair_nis(texto):
    linhas = obter_linhas(
        texto
    )

    for i, linha in enumerate(
        linhas
    ):
        if not contem_algum(
            linha,
            [
                "NIS",
                "PIS",
                "PASEP"
            ]
        ):
            continue

        bloco = contexto_linhas(
            linhas,
            i,
            antes=0,
            depois=2
        )

        candidatos = re.findall(
            r"(?<!\d)"
            r"\d{11}"
            r"(?!\d)",
            bloco
        )

        for numero in candidatos:
            if cpf_valido(
                numero
            ):
                continue

            return numero

    return ""


# ============================================================
# SUS / CNS
# ============================================================

def extrair_sus(texto):
    linhas = obter_linhas(
        texto
    )

    for i, linha in enumerate(
        linhas
    ):
        if not contem_algum(
            linha,
            [
                "CNS",
                "CARTAO SUS",
                "CARTAO NACIONAL DE SAUDE"
            ]
        ):
            continue

        bloco = contexto_linhas(
            linhas,
            i,
            antes=0,
            depois=3
        )

        candidatos = re.findall(
            r"(?<!\d)"
            r"\d{15}"
            r"(?!\d)",
            bloco
        )

        if candidatos:
            return candidatos[0]

    return ""


# ============================================================
# DAP
# ============================================================

def extrair_dap(texto):
    linhas = obter_linhas(
        texto
    )

    for i, linha in enumerate(
        linhas
    ):
        if "DAP" not in (
            normalizar_texto(
                linha
            )
        ):
            continue

        bloco = contexto_linhas(
            linhas,
            i,
            antes=0,
            depois=2
        )

        match = re.search(
            r"(?i)\bDAP\b"
            r"\s*[:\-]?\s*"
            r"([A-Z0-9./\-]{5,30})",
            bloco
        )

        if match:
            return (
                match.group(1)
                .strip()
                .upper()
            )

    return ""


# ============================================================
# EXTRAÇÃO UNIVERSAL
# ============================================================

def extrair_campos(texto):
    """
    MOTOR UNIVERSAL.

    Não pergunta qual é o tipo do documento.

    Procura cada campo de forma independente
    em TODO o conteúdo recebido.
    """

    dados = resultado_vazio()

    # Identificação pessoal
    dados["cpf"] = (
        extrair_cpf(
            texto
        )
    )

    dados["nome"] = (
        extrair_nome(
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

    # Dados eleitorais
    dados["titulo"] = (
        extrair_titulo(
            texto
        )
    )

    (
        dados["zona"],
        dados["secao"]
    ) = extrair_zona_secao(
        texto,
        dados["titulo"]
    )

    # Localização
    dados["cidade"] = (
        extrair_cidade(
            texto
        )
    )

    endereco = (
        extrair_endereco(
            texto
        )
    )

    dados["endereco"] = (
        endereco.get(
            "endereco",
            ""
        )
    )

    dados["numero"] = (
        endereco.get(
            "numero",
            ""
        )
    )

    dados["bairro"] = (
        endereco.get(
            "bairro",
            ""
        )
    )

    # Contato
    dados["telefone"] = (
        extrair_telefone(
            texto
        )
    )

    # Outros documentos
    dados["nis"] = (
        extrair_nis(
            texto
        )
    )

    dados["sus"] = (
        extrair_sus(
            texto
        )
    )

    dados["dap"] = (
        extrair_dap(
            texto
        )
    )

    return dados


# ============================================================
# COMPATIBILIDADE COM O APP ATUAL
# ============================================================

def identificar_documentos(texto):
    """
    Mantida somente para compatibilidade
    com chamadas antigas do app.

    NÃO é utilizada para decidir como
    os campos serão extraídos.
    """

    encontrados = []

    texto_norm = normalizar_texto(
        texto
    )

    if contem_algum(
        texto_norm,
        [
            "TITULO ELEITORAL",
            "JUSTICA ELEITORAL"
        ]
    ):
        encontrados.append(
            "TITULO_ELEITORAL"
        )

    if contem_algum(
        texto_norm,
        [
            "REGISTRO GERAL",
            "CARTEIRA DE IDENTIDADE",
            "INSTITUTO DE IDENTIFICACAO",
            "FILIACAO"
        ]
    ):
        encontrados.append(
            "IDENTIDADE"
        )

    if contem_algum(
        texto_norm,
        [
            "CARTEIRA NACIONAL DE HABILITACAO",
            "HABILITACAO"
        ]
    ):
        encontrados.append(
            "CNH"
        )

    if contem_algum(
        texto_norm,
        [
            "CEP",
            "ENDERECO",
            "COMPROVANTE DE RESIDENCIA"
        ]
    ):
        encontrados.append(
            "COMPROVANTE_ENDERECO"
        )

    if not encontrados:
        encontrados.append(
            "DOCUMENTO_NAO_IDENTIFICADO"
        )

    return encontrados


def separar_blocos_documentos(texto):
    """
    Mantida para compatibilidade.

    O extrator universal não depende
    desses blocos.
    """

    return {
        "DOCUMENTO_COMPLETO":
            str(texto or "").strip()
    }


def analisar_documentos(texto):
    """
    Interface compatível com o restante
    do projeto.
    """

    return {
        "documentos":
            identificar_documentos(
                texto
            ),

        "blocos":
            separar_blocos_documentos(
                texto
            ),

        "dados":
            extrair_campos(
                texto
            )
    }
