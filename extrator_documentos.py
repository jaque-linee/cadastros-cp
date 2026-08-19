from pathlib import Path
import re

src = Path("/mnt/data/Texto colado(20260819-114132).txt")
texto = src.read_text(encoding="utf-8")

novo_nome = r'''def extrair_nome(texto):
    """
    Extrai o nome sem depender do tipo de documento.
    Prioriza rótulos fortes e usa CPF como âncora somente como fallback.
    """
    linhas = obter_linhas(texto)

    # 1. NOME DO ELEITOR
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)

        if "NOME DO ELEITOR" not in n:
            continue

        resto = re.sub(
            r"(?i).*NOME\s+DO\s+ELEITOR\s*[:\-]*",
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

    # 2. NOME / NAME ou NOME
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
            r"(?i)^.*?\bNOME\b(?:\s*/\s*NAME)?\s*[:\-]*",
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

    # 3. REGISTRO CIVIL
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

    # 4. Fallback: nome válido imediatamente antes do CPF.
    indice_cpf = None

    for i, linha in enumerate(linhas):
        if "CPF" in normalizar_texto(linha):
            indice_cpf = i
            break

    if indice_cpf is not None:
        candidatos = []

        for j in range(max(0, indice_cpf - 8), indice_cpf):
            candidato = limpar_nome(linhas[j])

            if parece_nome(candidato):
                candidatos.append(candidato)

        if candidatos:
            return candidatos[-1]

    return ""
'''

novo_mae = r'''def extrair_nome_mae(
    texto,
    nome_pessoa=""
):
    """
    Extrai o nome da mãe por rótulo explícito ou pelo bloco de filiação.
    Não inventa mãe quando não houver evidência suficiente.
    """
    linhas = obter_linhas(texto)
    nome_pessoa_norm = normalizar_texto(nome_pessoa)

    # 1. Rótulo explícito MÃE / NOME DA MÃE
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)

        if not (
            "NOME DA MAE" in n
            or re.search(r"\bMAE\b", n)
        ):
            continue

        resto = re.sub(
            r"(?i).*?(?:NOME\s+DA\s+M[AÃ]E|M[AÃ]E)\s*[:\-]*",
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

    # 2. FILIAÇÃO: normalmente pai e mãe em sequência.
    for i, linha in enumerate(linhas):
        if "FILIACAO" not in normalizar_texto(linha):
            continue

        nomes = []

        resto = re.sub(
            r"(?i).*FILI[AÇC][AÃA]O\s*[:\-]*",
            "",
            linha
        ).strip()

        for parte in re.split(r"\s{2,}|[|;]", resto):
            candidato = limpar_nome(parte)

            if (
                parece_nome(candidato)
                and normalizar_texto(candidato) != nome_pessoa_norm
                and candidato not in nomes
            ):
                nomes.append(candidato)

        for j in range(i + 1, min(i + 10, len(linhas))):
            linha_j = linhas[j]
            nj = normalizar_texto(linha_j)

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

            if normalizar_texto(candidato) == nome_pessoa_norm:
                continue

            if candidato not in nomes:
                nomes.append(candidato)

        if len(nomes) >= 2:
            return nomes[1]

    # 3. OCR pode jogar os nomes da filiação antes do rótulo.
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
'''

novo_rg = r'''def extrair_rg(texto):
    """
    Extrai RG sem confundir CPF e datas.
    """
    linhas = obter_linhas(texto)
    cpf_num = somente_numeros(extrair_cpf(texto))

    # 1. REGISTRO GERAL
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)

        if "REGISTRO GERAL" not in n:
            continue

        bloco = contexto_linhas(linhas, i, antes=0, depois=3)

        bloco = re.sub(
            r"\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}\b",
            " ",
            bloco
        )

        candidatos = re.findall(
            r"(?<!\d)\d[\d.\-\s]{4,15}\d(?!\d)",
            bloco
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

    # 2. Rótulo RG isolado
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)

        if not re.search(r"\bRG\b", n):
            continue

        # Evita interpretar "ÓRGÃO" como RG.
        if "ORGAO" in n and not re.search(r"(^|\s)RG(\s|$|[:\-])", n):
            continue

        bloco = contexto_linhas(linhas, i, antes=0, depois=2)

        bloco = re.sub(
            r"\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}\b",
            " ",
            bloco
        )

        candidatos = re.findall(
            r"(?<!\d)\d{5,12}(?!\d)",
            bloco
        )

        for numero in candidatos:
            if numero == cpf_num:
                continue

            if len(numero) == 11 and cpf_valido(numero):
                continue

            return numero

    return ""
'''

novo_titulo = r'''def extrair_titulo(texto):
    """
    Extrai título eleitoral de 12 dígitos.
    Aceita também OCR com espaços ou separadores entre os algarismos.
    """
    texto = str(texto or "")
    linhas = obter_linhas(texto)
    candidatos = []

    # 1. Procura perto de INSCRIÇÃO.
    for i, linha in enumerate(linhas):
        if "INSCRICAO" not in normalizar_texto(linha):
            continue

        bloco = contexto_linhas(linhas, i, antes=1, depois=4)

        for match in re.finditer(
            r"(?<!\d)(?:\d[\s|.\-]*){12}(?!\d)",
            bloco
        ):
            numero = somente_numeros(match.group())

            if len(numero) == 12:
                candidatos.append((100, numero))

    # 2. Procura qualquer sequência exata de 12 dígitos e pontua contexto.
    for match in re.finditer(
        r"(?<!\d)\d{12}(?!\d)",
        texto
    ):
        numero = match.group()

        pontos = pontuar_titulo(
            texto,
            match.start(),
            match.end()
        )

        candidatos.append((pontos, numero))

    if not candidatos:
        return ""

    candidatos.sort(
        key=lambda item: item[0],
        reverse=True
    )

    melhor_pontos, melhor = candidatos[0]

    if melhor_pontos < 3:
        return ""

    return melhor
'''

novo_zona = r'''def extrair_zona_secao(
    texto,
    titulo=""
):
    """
    Extrai zona e seção pelo rótulo e, se necessário,
    usa o título eleitoral como âncora.
    """
    linhas = obter_linhas(texto)
    zona = ""
    secao = ""

    # 1. Rótulos diretos
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)

        if "ZONA" not in n and "SECAO" not in n:
            continue

        bloco = contexto_linhas(
            linhas,
            i,
            antes=0,
            depois=3
        )

        if not zona:
            mz = re.search(
                r"(?i)\bZONA\b[^0-9]{0,30}(\d{1,3})",
                bloco
            )

            if mz:
                zona = mz.group(1).zfill(3)

        if not secao:
            ms = re.search(
                r"(?i)SE[CÇ][AÃ]O[^0-9]{0,30}(\d{1,4})",
                bloco
            )

            if ms:
                secao = ms.group(1).zfill(4)

        if zona and secao:
            return zona, secao

    # 2. Título como âncora
    if titulo and (not zona or not secao):
        texto_str = str(texto or "")
        pos = texto_str.find(titulo)

        if pos >= 0:
            trecho = texto_str[
                max(0, pos - 120):
                min(len(texto_str), pos + len(titulo) + 220)
            ]

            pos_local = trecho.find(titulo)
            depois = trecho[pos_local + len(titulo):]

            # Remove datas para não capturar dia/mês/ano como zona/seção.
            depois = re.sub(
                r"\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}\b",
                " ",
                depois
            )

            numeros = re.findall(
                r"(?<!\d)\d{1,4}(?!\d)",
                depois
            )

            candidatos = []

            for numero in numeros:
                valor = int(numero)

                if 0 < valor <= 9999:
                    candidatos.append(numero)

            if not zona:
                for numero in candidatos:
                    if len(numero) <= 3:
                        zona = numero.zfill(3)
                        break

            if not secao and zona:
                achou_zona = False

                for numero in candidatos:
                    if not achou_zona and numero.zfill(3) == zona:
                        achou_zona = True
                        continue

                    if achou_zona:
                        secao = numero.zfill(4)
                        break

    # 3. Tabela eleitoral achatada pelo OCR:
    # nascimento + título + zona + seção
    if not zona or not secao:
        padrao = re.compile(
            r"(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4})"
            r".{0,100}?"
            r"(\d{12})"
            r".{0,50}?"
            r"(\d{1,3})"
            r".{0,50}?"
            r"(\d{1,4})",
            re.S
        )

        match = padrao.search(str(texto or ""))

        if match:
            titulo_encontrado = match.group(2)

            if not titulo or titulo_encontrado == titulo:
                if not zona:
                    zona = match.group(3).zfill(3)

                if not secao:
                    secao = match.group(4).zfill(4)

    return zona, secao
'''

def substituir_funcao(codigo, nome, nova_funcao):
    padrao = re.compile(
        rf"^def {re.escape(nome)}\s*\(.*?(?=^def |\Z)",
        re.M | re.S
    )
    m = padrao.search(codigo)
    if not m:
        raise ValueError(f"Função não encontrada: {nome}")
    return codigo[:m.start()] + nova_funcao.rstrip() + "\n\n\n" + codigo[m.end():]

for nome, nova in [
    ("extrair_nome", novo_nome),
    ("extrair_nome_mae", novo_mae),
    ("extrair_rg", novo_rg),
    ("extrair_titulo", novo_titulo),
    ("extrair_zona_secao", novo_zona),
]:
    texto = substituir_funcao(texto, nome, nova)

destino = Path("/mnt/data/extrator_documentos.py")
destino.write_text(texto, encoding="utf-8")

# valida sintaxe antes de entregar
compile(texto, str(destino), "exec")

print(f"Arquivo completo criado e validado: {destino}")
print(f"{len(texto.splitlines())} linhas")
