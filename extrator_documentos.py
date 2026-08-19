# ============================================================
# NOME - UNIVERSAL
# ============================================================

def extrair_nome(texto):
    linhas = obter_linhas(texto)

    # --------------------------------------------------------
    # 1. NOME DO ELEITOR
    # --------------------------------------------------------
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)

        if "NOME DO ELEITOR" not in n:
            continue

        # Pode estar na mesma linha
        resto = re.sub(
            r"(?i).*NOME\s+DO\s+ELEITOR\s*[:\-]*",
            "",
            linha
        ).strip()

        candidato = limpar_nome(resto)

        if parece_nome(candidato):
            return candidato

        # Ou nas próximas linhas
        for j in range(i + 1, min(i + 5, len(linhas))):
            candidato = limpar_nome(linhas[j])

            if parece_nome(candidato):
                return candidato

    # --------------------------------------------------------
    # 2. CAMPO NOME / NAME
    # --------------------------------------------------------
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)

        if "NOME DO ELEITOR" in n:
            continue

        if not (
            n == "NOME"
            or n.startswith("NOME ")
            or "NOME / NAME" in n
            or "NOME/NAME" in n
        ):
            continue

        resto = re.sub(
            r"(?i)^.*?\bNOME\b"
            r"(?:\s*/\s*NAME)?"
            r"\s*[:\-]*",
            "",
            linha
        ).strip()

        candidato = limpar_nome(resto)

        if parece_nome(candidato):
            return candidato

        for j in range(i + 1, min(i + 5, len(linhas))):
            candidato = limpar_nome(linhas[j])

            if parece_nome(candidato):
                return candidato

    # --------------------------------------------------------
    # 3. REGISTRO CIVIL
    # Em RG antigo o nome pode aparecer perto desse rótulo
    # --------------------------------------------------------
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)

        if "REGISTRO CIVIL" not in n:
            continue

        resto = re.sub(
            r"(?i).*REGISTRO\s+CIVIL\s*[:\-]*",
            "",
            linha
        ).strip()

        candidato = limpar_nome(resto)

        if parece_nome(candidato):
            return candidato

        for j in range(i + 1, min(i + 4, len(linhas))):
            candidato = limpar_nome(linhas[j])

            if parece_nome(candidato):
                return candidato

    # --------------------------------------------------------
    # 4. NOME PRÓXIMO AO CPF
    # Fallback para RG/CIN com OCR bagunçado
    # --------------------------------------------------------
    indice_cpf = None

    for i, linha in enumerate(linhas):
        if "CPF" in normalizar_texto(linha):
            indice_cpf = i
            break

    if indice_cpf is not None:
        inicio = max(0, indice_cpf - 8)

        candidatos = []

        for j in range(inicio, indice_cpf):
            candidato = limpar_nome(linhas[j])

            if parece_nome(candidato):
                candidatos.append(candidato)

        if candidatos:
            # O nome costuma ser o candidato válido
            # mais próximo do CPF.
            return candidatos[-1]

    return ""


# ============================================================
# NOME DA MÃE / FILIAÇÃO
# ============================================================

def extrair_nome_mae(texto, nome_pessoa=""):
    linhas = obter_linhas(texto)

    nome_pessoa_norm = normalizar_texto(nome_pessoa)

    # --------------------------------------------------------
    # 1. CAMPO EXPLÍCITO MÃE
    # --------------------------------------------------------
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)

        if not (
            "NOME DA MAE" in n
            or re.search(r"\bMAE\b", n)
        ):
            continue

        resto = re.sub(
            r"(?i).*?(?:NOME\s+DA\s+M[AÃ]E|M[AÃ]E)"
            r"\s*[:\-]*",
            "",
            linha
        ).strip()

        candidato = limpar_nome(resto)

        if (
            parece_nome(candidato)
            and normalizar_texto(candidato) != nome_pessoa_norm
        ):
            return candidato

        for j in range(i + 1, min(i + 4, len(linhas))):
            candidato = limpar_nome(linhas[j])

            if (
                parece_nome(candidato)
                and normalizar_texto(candidato) != nome_pessoa_norm
            ):
                return candidato

    # --------------------------------------------------------
    # 2. FILIAÇÃO
    # --------------------------------------------------------
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)

        if not (
            "FILIACAO" in n
            or "FILIAÇAO" in linha.upper()
            or "FILIAÇÃO" in linha.upper()
        ):
            continue

        nomes = []

        # Conteúdo após FILIAÇÃO na mesma linha
        resto = re.sub(
            r"(?i).*?FILI[AÇC][AÃA]O\s*[:\-]*",
            "",
            linha
        ).strip()

        # Pode haver dois nomes na mesma linha
        partes = re.split(
            r"\s{2,}|[|;]",
            resto
        )

        for parte in partes:
            candidato = limpar_nome(parte)

            if not parece_nome(candidato):
                continue

            if normalizar_texto(candidato) == nome_pessoa_norm:
                continue

            if candidato not in nomes:
                nomes.append(candidato)

        # Linhas seguintes
        for j in range(i + 1, min(i + 10, len(linhas))):
            linha_j = linhas[j]
            nj = normalizar_texto(linha_j)

            # Campos que normalmente encerram filiação
            if contem_algum(
                nj,
                [
                    "DATA NASCIMENTO",
                    "DATA DE NASCIMENTO",
                    "NASCIMENTO",
                    "NATURALIDADE",
                    "ORGAO EXPEDIDOR",
                    "DATA EXPEDICAO",
                    "DATA DE EXPEDICAO",
                    "VALIDADE",
                    "ASSINATURA"
                ]
            ):
                break

            candidato = limpar_nome(linha_j)

            if not parece_nome(candidato):
                continue

            cn = normalizar_texto(candidato)

            if cn == nome_pessoa_norm:
                continue

            if candidato not in nomes:
                nomes.append(candidato)

        # Padrão brasileiro:
        # normalmente pai + mãe.
        if len(nomes) >= 2:
            return nomes[1]

    # --------------------------------------------------------
    # 3. FILIAÇÃO PODE VIR ANTES DO RÓTULO
    # OCR às vezes inverte a ordem visual
    # --------------------------------------------------------
    for i, linha in enumerate(linhas):
        if "FILIACAO" not in normalizar_texto(linha):
            continue

        candidatos = []

        for j in range(max(0, i - 5), i):
            candidato = limpar_nome(linhas[j])

            if (
                parece_nome(candidato)
                and normalizar_texto(candidato) != nome_pessoa_norm
            ):
                candidatos.append(candidato)

        if len(candidatos) >= 2:
            return candidatos[-1]

    return ""


# ============================================================
# RG - UNIVERSAL
# ============================================================

def extrair_rg(texto):
    linhas = obter_linhas(texto)

    # --------------------------------------------------------
    # 1. REGISTRO GERAL
    # --------------------------------------------------------
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)

        if "REGISTRO GERAL" not in n:
            continue

        bloco = contexto_linhas(
            linhas,
            i,
            antes=0,
            depois=3
        )

        # Remove CPF
        cpf = extrair_cpf(bloco)

        cpf_num = somente_numeros(cpf)

        # Remove datas
        bloco_sem_datas = re.sub(
            r"\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}\b",
            " ",
            bloco
        )

        candidatos = re.findall(
            r"(?<!\d)"
            r"\d[\d.\-\s]{4,15}\d"
            r"(?!\d)",
            bloco_sem_datas
        )

        for candidato in candidatos:
            numero = somente_numeros(candidato)

            if not (5 <= len(numero) <= 12):
                continue

            if numero == cpf_num:
                continue

            if len(numero) == 11 and cpf_valido(numero):
                continue

            return numero

    # --------------------------------------------------------
    # 2. RÓTULO RG
    # --------------------------------------------------------
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)

        if not re.search(r"\bRG\b", n):
            continue

        bloco = contexto_linhas(
            linhas,
            i,
            antes=0,
            depois=2
        )

        # Evita "ÓRGÃO"
        if (
            "ORGAO" in n
            and n.find("ORGAO") <= n.find("RG")
        ):
            continue

        candidatos = re.findall(
            r"(?<!\d)\d{5,12}(?!\d)",
            bloco
        )

        for numero in candidatos:
            if len(numero) == 11 and cpf_valido(numero):
                continue

            return numero

    # --------------------------------------------------------
    # 3. "REGISTRO" ISOLADO
    # --------------------------------------------------------
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)

        if "REGISTRO" not in n:
            continue

        if contem_algum(
            n,
            [
                "REGISTRO CIVIL",
                "REGISTRO PROFISSIONAL"
            ]
        ):
            continue

        candidatos = re.findall(
            r"(?<!\d)\d{5,12}(?!\d)",
            contexto_linhas(
                linhas,
                i,
                antes=0,
                depois=2
            )
        )

        for numero in candidatos:
            if len(numero) == 11 and cpf_valido(numero):
                continue

            return numero

    return ""


# ============================================================
# TÍTULO ELEITORAL
# ============================================================

def extrair_titulo(texto):
    linhas = obter_linhas(texto)

    candidatos = []

    # --------------------------------------------------------
    # 1. INSCRIÇÃO
    # --------------------------------------------------------
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)

        if "INSCRICAO" not in n:
            continue

        bloco = contexto_linhas(
            linhas,
            i,
            antes=1,
            depois=4
        )

        # Aceita espaços entre os números causados pelo OCR
        numeros = re.findall(
            r"(?:\d[\s|]*){12}",
            bloco
        )

        for numero in numeros:
            numero = somente_numeros(numero)

            if len(numero) == 12:
                candidatos.append((100, numero))

    # --------------------------------------------------------
    # 2. TODOS OS NÚMEROS DE 12 DÍGITOS
    # pontuados pelo contexto eleitoral
    # --------------------------------------------------------
    texto_str = str(texto or "")

    for match in re.finditer(
        r"(?<!\d)\d{12}(?!\d)",
        texto_str
    ):
        numero = match.group()

        contexto = normalizar_texto(
            texto_str[
                max(0, match.start() - 180):
                min(len(texto_str), match.end() + 180)
            ]
        )

        pontos = 0

        if "INSCRICAO" in contexto:
            pontos += 20

        if "TITULO ELEITORAL" in contexto:
            pontos += 20

        if "JUSTICA ELEITORAL" in contexto:
            pontos += 15

        if "ZONA" in contexto:
            pontos += 10

        if "SECAO" in contexto:
            pontos += 10

        if "NOME DO ELEITOR" in contexto:
            pontos += 10

        candidatos.append(
            (pontos, numero)
        )

    if not candidatos:
        return ""

    candidatos.sort(
        key=lambda x: x[0],
        reverse=True
    )

    melhor_pontuacao, melhor_numero = candidatos[0]

    if melhor_pontuacao < 10:
        return ""

    return melhor_numero


# ============================================================
# ZONA E SEÇÃO
# ============================================================

def extrair_zona_secao(texto, titulo=""):
    linhas = obter_linhas(texto)

    zona = ""
    secao = ""

    # --------------------------------------------------------
    # 1. PROCURA LINHA QUE TENHA ZONA E SEÇÃO
    # --------------------------------------------------------
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)

        if (
            "ZONA" not in n
            and "SECAO" not in n
        ):
            continue

        bloco = contexto_linhas(
            linhas,
            i,
            antes=0,
            depois=3
        )

        # Zona explícita
        mz = re.search(
            r"(?i)\bZONA\b"
            r"[^0-9]{0,30}"
            r"(\d{1,3})",
            bloco
        )

        if mz:
            zona = mz.group(1).zfill(3)

        # Seção explícita
        ms = re.search(
            r"(?i)"
            r"SE[CÇ][AÃ]O"
            r"[^0-9]{0,30}"
            r"(\d{1,4})",
            bloco
        )

        if ms:
            secao = ms.group(1).zfill(4)

        if zona and secao:
            return zona, secao

    # --------------------------------------------------------
    # 2. USA O TÍTULO COMO ÂNCORA
    # --------------------------------------------------------
    if titulo:
        texto_str = str(texto or "")

        pos = texto_str.find(titulo)

        if pos >= 0:
            trecho = texto_str[
                max(0, pos - 150):
                min(
                    len(texto_str),
                    pos + len(titulo) + 250
                )
            ]

            # Remove o próprio título
            trecho = trecho.replace(
                titulo,
                " "
            )

            # Remove datas
            trecho = re.sub(
                r"\b\d{1,2}"
                r"[/.\-]"
                r"\d{1,2}"
                r"[/.\-]"
                r"\d{4}\b",
                " ",
                trecho
            )

            numeros = re.findall(
                r"(?<!\d)"
                r"\d{1,4}"
                r"(?!\d)",
                trecho
            )

            candidatos = []

            for numero in numeros:
                valor = int(numero)

                if 1 <= valor <= 9999:
                    candidatos.append(numero)

            # Procura zona típica de até 3 dígitos
            if not zona:
                for numero in candidatos:
                    if len(numero) <= 3:
                        zona = numero.zfill(3)
                        break

            # Seção normalmente vem depois da zona
            if not secao and zona:
                achou_zona = False

                for numero in candidatos:
                    if (
                        numero.zfill(3) == zona
                        and not achou_zona
                    ):
                        achou_zona = True
                        continue

                    if achou_zona:
                        secao = numero.zfill(4)
                        break

    # --------------------------------------------------------
    # 3. CASO OCR TENHA LIDO A TABELA TODA EM UMA LINHA
    #
    # nascimento + título + zona + seção
    # --------------------------------------------------------
    texto_norm = str(texto or "")

    padrao = re.compile(
        r"(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})"
        r".{0,80}?"
        r"(\d{12})"
        r".{0,40}?"
        r"(\d{1,3})"
        r".{0,40}?"
        r"(\d{1,4})",
        re.S
    )

    match = padrao.search(
        texto_norm
    )

    if match:
        titulo_encontrado = match.group(2)

        if (
            not titulo
            or titulo_encontrado == titulo
        ):
            if not zona:
                zona = match.group(3).zfill(3)

            if not secao:
                secao = match.group(4).zfill(4)

    return zona, secao
