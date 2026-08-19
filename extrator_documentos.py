import re
import unicodedata
from datetime import datetime


# ============================================================
# ESTRUTURA PADRÃO
# ============================================================

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
# NORMALIZAÇÃO
# ============================================================

def remover_acentos(texto):
    texto = str(texto or "")
    return "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def normalizar_texto(texto):
    texto = remover_acentos(texto).upper()
    texto = texto.replace("º", "O")
    texto = texto.replace("°", "O")
    texto = re.sub(r"[ \t]+", " ", texto)
    return texto.strip()


def normalizar_linha(texto):
    return normalizar_texto(texto)


def somente_numeros(valor):
    return re.sub(r"\D", "", str(valor or ""))


def obter_linhas(texto):
    return [
        linha.strip()
        for linha in str(texto or "").splitlines()
        if linha.strip()
    ]


# ============================================================
# VALIDAÇÕES
# ============================================================

def cpf_valido(cpf):
    cpf = somente_numeros(cpf)
    if len(cpf) != 11:
        return False
    if cpf == cpf[0] * 11:
        return False
    try:
        soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
        digito = 11 - soma % 11
        if digito >= 10:
            digito = 0
        if digito != int(cpf[9]):
            return False
        soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
        digito = 11 - soma % 11
        if digito >= 10:
            digito = 0
        return digito == int(cpf[10])
    except Exception:
        return False


def formatar_cpf(cpf):
    cpf = somente_numeros(cpf)
    if len(cpf) != 11:
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def data_valida(data):
    try:
        datetime.strptime(data, "%d/%m/%Y")
        return True
    except Exception:
        return False


# ============================================================
# LIMPEZA DE NOMES
# ============================================================

PALAVRAS_INVALIDAS_NOME = {
    "REPUBLICA", "FEDERATIVA", "BRASIL", "ESTADO",
    "SECRETARIA", "SEGURANCA", "PUBLICA", "PERICIA",
    "OFICIAL", "INSTITUTO", "IDENTIFICACAO", "CARTEIRA",
    "IDENTIDADE", "JUSTICA", "ELEITORAL", "TITULO",
    "REGISTRO", "GERAL", "NASCIMENTO", "NATURALIDADE",
    "MUNICIPIO", "INSCRICAO", "SECAO", "ZONA",
    "CPF", "ORGAO", "EXPEDIDOR", "DATA",
    "EMISSAO", "EXPEDICAO", "ASSINATURA", "VALIDADE",
    "POLEGAR", "DIREITO"
}


def limpar_nome(valor):
    valor = str(valor or "")
    valor = re.sub(r"^[^A-Za-zÀ-ÿ]+", "", valor)
    valor = re.sub(r"[^A-Za-zÀ-ÿ'\s]", " ", valor)
    valor = re.sub(r"\s+", " ", valor)
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
    normalizadas = [normalizar_texto(p) for p in palavras]
    invalidas = sum(p in PALAVRAS_INVALIDAS_NOME for p in normalizadas)
    if invalidas >= 2:
        return False
    if invalidas >= max(1, len(palavras) - 1):
        return False
    return True


# ============================================================
# IDENTIFICAÇÃO DOS DOCUMENTOS
# ============================================================

def identificar_documentos(texto):
    t = normalizar_texto(texto)
    documentos = []

    titulo_pontos = sum(
        termo in t
        for termo in [
            "TITULO ELEITORAL", "JUSTICA ELEITORAL",
            "NOME DO ELEITOR", "INSCRICAO", "ZONA", "SECAO"
        ]
    )
    if titulo_pontos >= 2:
        documentos.append("TITULO_ELEITORAL")

    identidade_pontos = sum(
        termo in t
        for termo in [
            "CARTEIRA DE IDENTIDADE", "REGISTRO GERAL",
            "REGISTRO CIVIL", "INSTITUTO DE IDENTIFICACAO",
            "FILIACAO", "NATURALIDADE", "ORGAO EXPEDIDOR"
        ]
    )
    if identidade_pontos >= 2:
        documentos.append("IDENTIDADE")

    if "CARTEIRA NACIONAL DE HABILITACAO" in t or ("HABILITACAO" in t and "CATEGORIA" in t):
        documentos.append("CNH")

    endereco_pontos = sum(
        termo in t
        for termo in ["CEP", "ENDERECO", "RUA", "AVENIDA", "BAIRRO", "VENCIMENTO", "FATURA"]
    )
    if endereco_pontos >= 3:
        documentos.append("COMPROVANTE_ENDERECO")

    if any(termo in t for termo in ["CARTAO NACIONAL DE SAUDE", "CARTAO SUS", "SISTEMA UNICO DE SAUDE", "CNS"]):
        documentos.append("CARTAO_SUS")

    if not documentos:
        documentos.append("DOCUMENTO_NAO_IDENTIFICADO")

    return documentos


# ============================================================
# LOCALIZAR LINHAS PRÓXIMAS A UM RÓTULO
# ============================================================

def localizar_indice(linhas, termos):
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)
        if any(termo in n for termo in termos):
            return i
    return None


def trecho_proximo(linhas, indice, antes=0, depois=4):
    if indice is None:
        return ""
    inicio = max(0, indice - antes)
    fim = min(len(linhas), indice + depois + 1)
    return "\n".join(linhas[inicio:fim])


# ============================================================
# CPF
# ============================================================

def extrair_cpf(texto):
    texto = str(texto or "")
    padrao = re.compile(r"(?<!\d)(\d{3})[\.\s]?(\d{3})[\.\s]?(\d{3})[\-\s]?(\d{2})(?!\d)")
    for m in padrao.finditer(texto):
        cpf = "".join(m.groups())
        if cpf_valido(cpf):
            return formatar_cpf(cpf)
    for numero in re.findall(r"(?<!\d)\d{11}(?!\d)", texto):
        if cpf_valido(numero):
            return formatar_cpf(numero)
    for numero in re.findall(r"\d{11}", texto):
        if cpf_valido(numero):
            return formatar_cpf(numero)
    return ""


# ============================================================
# DATA DE NASCIMENTO
# ============================================================

def extrair_data_nascimento(texto):
    linhas = obter_linhas(texto)
    padrao = re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b")

    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)
        if not any(termo in n for termo in ["NASCIMENTO", "DATA NASC", "DATE OF BIRTH"]):
            continue
        bloco = trecho_proximo(linhas, i, antes=0, depois=3)
        for m in padrao.finditer(bloco):
            data = f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
            if data_valida(data):
                return data

    candidatos = []
    for m in padrao.finditer(texto):
        data = f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
        if not data_valida(data):
            continue
        ano = int(m.group(3))
        if 1900 <= ano <= 2015:
            candidatos.append(data)
    return candidatos[0] if candidatos else ""


# ============================================================
# NOME DO TÍTULO (PRIORITÁRIO)
# ============================================================

def extrair_nome_titulo(texto):
    """
    Extrai o nome do Título Eleitoral com prioridade máxima.
    PRIORIDADE 1: Padrão "NOME DO ELEITOR | NOME"
    """
    linhas = obter_linhas(texto)
    
    # PRIORIDADE 1: Padrão "NOME DO ELEITOR | NOME"
    padrao_barra = r"NOME\s+DO\s+ELEITOR\s*[|]\s*([A-ZÀ-Ÿ\s]+?)(?=\s*(?:DATA|INSCRICAO|ZONA|SECAO|$)|\n)"
    match = re.search(padrao_barra, texto, re.I)
    if match:
        nome = match.group(1).strip().upper()
        nome = re.sub(r"[^A-ZÀ-Ÿ\s]", "", nome).strip()
        if parece_nome(nome) and len(nome.split()) >= 2:
            return nome
    
    # PRIORIDADE 2: Tabela com barra vertical
    padrao_tabela = r"NOME\s+DO\s+ELEITOR\s*\|?\s*([A-ZÀ-Ÿ\s]+?)(?=\s*\|?\s*DATA\s+DE|\s*INSCRICAO|\s*ZONA|\s*SECAO|\n|$)"
    match = re.search(padrao_tabela, texto, re.I)
    if match:
        nome = match.group(1).strip().upper()
        nome = re.sub(r"[^A-ZÀ-Ÿ\s]", "", nome).strip()
        if parece_nome(nome) and len(nome.split()) >= 2:
            return nome
    
    # PRIORIDADE 3: Busca linha a linha
    indice = localizar_indice(linhas, ["NOME DO ELEITOR"])
    if indice is None:
        return ""

    linha = linhas[indice]
    resto = re.sub(r"(?i).*NOME\s+DO\s+ELEITOR", "", linha)
    resto = limpar_nome(resto)
    if parece_nome(resto):
        return resto

    for j in range(indice + 1, min(indice + 5, len(linhas))):
        candidato = limpar_nome(linhas[j])
        if parece_nome(candidato):
            return candidato

    return ""


# ============================================================
# NOME NO RG / CIN
# ============================================================

def extrair_nome_identidade(texto):
    linhas = obter_linhas(texto)

    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)
        if "NOME DO ELEITOR" in n:
            continue
        if not (n == "NOME" or n.startswith("NOME ") or "NOME / NAME" in n):
            continue
        resto = re.sub(r"(?i)^.*?\bNOME\b(?:\s*/\s*NAME)?\s*[:\-]*", "", linha)
        candidato = limpar_nome(resto)
        if parece_nome(candidato):
            return candidato
        for j in range(i + 1, min(i + 4, len(linhas))):
            candidato = limpar_nome(linhas[j])
            if parece_nome(candidato):
                return candidato

    for linha in linhas:
        n = normalizar_texto(linha)
        if "REGISTRO CIVIL" not in n:
            continue
        resto = re.sub(r"(?i).*REGISTRO\s+CIVIL", "", linha)
        candidato = limpar_nome(resto)
        if parece_nome(candidato):
            return candidato

    return ""


# ============================================================
# NOME PRINCIPAL
# ============================================================

def extrair_nome(texto):
    documentos = identificar_documentos(texto)
    if "TITULO_ELEITORAL" in documentos:
        nome = extrair_nome_titulo(texto)
        if nome:
            return nome
    nome = extrair_nome_identidade(texto)
    if nome:
        return nome
    return ""


# ============================================================
# RG
# ============================================================

def extrair_rg(texto):
    linhas = obter_linhas(texto)

    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)
        if "REGISTRO GERAL" not in n:
            continue
        resto = re.sub(r"(?i).*REGISTRO\s+GERAL", "", linha)
        candidatos = re.findall(r"\d[\d.\-\s]{3,15}\d", resto)
        for candidato in candidatos:
            numero = somente_numeros(candidato)
            if 5 <= len(numero) <= 12:
                return numero
        bloco = trecho_proximo(linhas, i, depois=2)
        candidatos = re.findall(r"(?<!\d)\d{5,12}(?!\d)", bloco)
        if candidatos:
            return candidatos[0]

    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)
        if not re.search(r"\bRG\b", n):
            continue
        candidatos = re.findall(r"\d[\d.\-\s]{3,15}\d", linha)
        for candidato in candidatos:
            numero = somente_numeros(candidato)
            if 5 <= len(numero) <= 12:
                return numero

    return ""


# ============================================================
# FILIAÇÃO / NOME DA MÃE (PRIORITÁRIO)
# ============================================================

def extrair_nome_mae(texto, nome_pessoa=""):
    """
    Extrai o nome da mãe com prioridade para FILIAÇÃO no RG.
    """
    linhas = obter_linhas(texto)
    nome_norm = normalizar_texto(nome_pessoa)

    # PRIORIDADE 1: FILIAÇÃO no RG
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)
        if "FILIACAO" not in n and "FILIAÇÃO" not in n:
            continue
        
        candidatos = []
        for j in range(i + 1, min(i + 6, len(linhas))):
            candidato = limpar_nome(linhas[j])
            if not candidato:
                continue
            if parece_nome(candidato) and len(candidato.split()) >= 2:
                if normalizar_texto(candidato) != nome_norm:
                    candidatos.append(candidato)
            rotulo = normalizar_texto(linhas[j])
            if rotulo in ["NATURALIDADE", "CPF", "RG", "REGISTRO", "EMISSAO", "DATA"]:
                break
        
        if len(candidatos) >= 2:
            filiacao_texto = " ".join(candidatos)
            if " E " in filiacao_texto or " & " in filiacao_texto:
                for sep in [" E ", " & ", ", "]:
                    if sep in filiacao_texto:
                        mae = filiacao_texto.split(sep)[-1].strip()
                        if parece_nome(mae):
                            return mae
            return candidatos[1]
        elif len(candidatos) == 1:
            return candidatos[0]

    # PRIORIDADE 2: NOME DA MAE no Título Eleitoral
    padrao_mae = r"NOME\s+DA\s+MAE\s*[:\-]?\s*([A-ZÀ-Ÿ\s]+?)(?=\s*(?:NOME\s+DO\s+PAI|DATA|CPF|RG|$)|\n)"
    match = re.search(padrao_mae, texto, re.I)
    if match:
        mae = match.group(1).strip().upper()
        mae = re.sub(r"[^A-ZÀ-Ÿ\s]", "", mae).strip()
        if parece_nome(mae) and len(mae.split()) >= 2:
            return mae

    # PRIORIDADE 3: Rótulo MAE
    for i, linha in enumerate(linhas):
        n = normalizar_texto(linha)
        if n == "MAE" or n.startswith("MAE "):
            for j in range(i + 1, min(i + 4, len(linhas))):
                candidato = limpar_nome(linhas[j])
                if parece_nome(candidato) and len(candidato.split()) >= 2:
                    if normalizar_texto(candidato) != nome_norm:
                        return candidato

    # PRIORIDADE 4: Nomes antes da NATURALIDADE (RG antigo)
    indice_naturalidade = None
    for i, linha in enumerate(linhas):
        if "NATURALIDADE" in normalizar_texto(linha):
            indice_naturalidade = i
            break

    if indice_naturalidade is not None:
        candidatos = []
        for j in range(max(0, indice_naturalidade - 8), indice_naturalidade):
            candidato = limpar_nome(linhas[j])
            if not parece_nome(candidato):
                continue
            if normalizar_texto(candidato) == nome_norm:
                continue
            candidatos.append(candidato)
        if len(candidatos) >= 2:
            return candidatos[-1]

    return ""


# ============================================================
# TÍTULO ELEITORAL (PRIORITÁRIO)
# ============================================================

def extrair_bloco_titulo(texto):
    linhas = obter_linhas(texto)
    inicio = localizar_indice(linhas, ["TITULO ELEITORAL", "JUSTICA ELEITORAL"])
    if inicio is None:
        return ""
    return "\n".join(linhas[inicio:min(inicio + 25, len(linhas))])


def extrair_titulo_zona_secao(texto):
    bloco = extrair_bloco_titulo(texto)
    if not bloco:
        return "", "", ""

    linhas = obter_linhas(bloco)
    titulo = ""
    zona = ""
    secao = ""

    # PRIORIDADE 1: Tabela do Título Eleitoral
    padrao_tabela = re.compile(
        r"(\d{1,2}/\d{1,2}/\d{4})"
        r".{0,40}?"
        r"(\d{12})"
        r".{0,25}?"
        r"(\d{1,3})"
        r".{0,25}?"
        r"(\d{1,4})",
        re.S
    )

    m = padrao_tabela.search(bloco)
    if m:
        if not titulo:
            titulo = m.group(2)
        if not zona:
            zona = m.group(3).zfill(3)
        if not secao:
            secao = m.group(4).zfill(4)

    # PRIORIDADE 2: Busca separada por rótulos
    indice_inscricao = localizar_indice(linhas, ["INSCRICAO"])
    if indice_inscricao is not None:
        trecho = trecho_proximo(linhas, indice_inscricao, antes=0, depois=3)
        candidatos = re.findall(r"(?<!\d)\d{12}(?!\d)", trecho)
        if candidatos:
            titulo = candidatos[0]

    if not titulo:
        candidatos = re.findall(r"(?<!\d)\d{12}(?!\d)", bloco)
        if candidatos:
            titulo = candidatos[0]

    indice_zona = localizar_indice(linhas, ["ZONA"])
    if indice_zona is not None:
        linha = linhas[indice_zona]
        m = re.search(r"(?i)\bZONA\b[^0-9]{0,12}(\d{1,3})", linha)
        if m:
            zona = m.group(1).zfill(3)

    indice_secao = localizar_indice(linhas, ["SECAO", "SEÇÃO"])
    if indice_secao is not None:
        linha = linhas[indice_secao]
        m = re.search(r"(?i)SE[CÇ][AÃ]O[^0-9]{0,12}(\d{1,4})", linha)
        if m:
            secao = m.group(1).zfill(4)

    # PRIORIDADE 3: Fallback
    if not titulo or not zona or not secao:
        for linha in linhas:
            numeros = re.findall(r"(?<!\d)\d{2,12}(?!\d)", linha)
            titulo_linha = [n for n in numeros if len(n) == 12]
            pequenos = [n for n in numeros if 1 <= len(n) <= 4]
            if titulo_linha and len(pequenos) >= 2:
                if not titulo:
                    titulo = titulo_linha[0]
                if not zona:
                    zona = pequenos[-2].zfill(3)
                if not secao:
                    secao = pequenos[-1].zfill(4)
                break

    return titulo, zona, secao
# ============================================================
# MUNICÍPIO / CIDADE
# ============================================================

def extrair_cidade(texto):
    linhas = obter_linhas(texto)

    # --------------------------------------------------------
    # MUNICÍPIO / UF do título eleitoral
    # --------------------------------------------------------

    indice = localizar_indice(
        linhas,
        [
            "MUNICIPIO / UF",
            "MUNICIPIO/UF",
            "MUNICIPIO"
        ]
    )

    if indice is not None:

        # Própria linha + seguintes.
        bloco = trecho_proximo(
            linhas,
            indice,
            depois=3
        )

        # Procura algo como ARAPIRACA / AL.
        matches = re.findall(
            r"\b"
            r"([A-ZÀ-Ÿ][A-ZÀ-Ÿ\s]{2,35}?)"
            r"\s*/\s*"
            r"([A-Z]{2})"
            r"\b",
            bloco,
            re.I
        )

        for cidade, uf in matches:

            cidade = limpar_nome(
                cidade
            )

            n = normalizar_texto(
                cidade
            )

            # Remove resíduos de rótulo.
            n = re.sub(
                r"^MUNICIPIO\s*UF\s*",
                "",
                n
            )

            n = re.sub(
                r"^MUNICIPIO\s*",
                "",
                n
            )

            n = re.sub(
                r"^[RLI]\s+MUNICIPIO\s*",
                "",
                n
            )

            if (
                n
                and "MUNICIPIO" not in n
            ):
                return n

    # --------------------------------------------------------
    # NATURALIDADE
    # Ex.: ARAPIRACA-AL
    # --------------------------------------------------------

    indice = localizar_indice(
        linhas,
        [
            "NATURALIDADE"
        ]
    )

    if indice is not None:

        bloco = trecho_proximo(
            linhas,
            indice,
            depois=2
        )

        m = re.search(
            r"([A-ZÀ-Ÿ][A-ZÀ-Ÿ\s]{2,35})"
            r"[-/]\s*"
            r"([A-Z]{2})",
            bloco,
            re.I
        )

        if m:

            cidade = limpar_nome(
                m.group(1)
            )

            cidade = re.sub(
                r"(?i)^.*NATURALIDADE\s*",
                "",
                cidade
            ).strip()

            if cidade:
                return cidade

    return ""


# ============================================================
# TELEFONE
# ============================================================

def extrair_telefone(texto):
    """
    Só aceita número com forte aparência de telefone.

    NÃO tenta transformar CPF, RG, título ou MRZ em telefone.
    """

    texto = str(texto or "")

    # Prioridade para telefone com DDD explicitamente
    # delimitado por parênteses.
    padrao_parenteses = re.compile(
        r"\("
        r"(\d{2})"
        r"\)"
        r"\s*"
        r"(9?\d{4})"
        r"[\s.\-]*"
        r"(\d{4})"
    )

    for m in padrao_parenteses.finditer(
        texto
    ):

        ddd = m.group(1)
        parte1 = m.group(2)
        parte2 = m.group(3)

        numero = (
            ddd
            + parte1
            + parte2
        )

        if len(numero) not in (
            10,
            11
        ):
            continue

        return (
            f"({ddd}) "
            f"{parte1}-{parte2}"
        )

    # Só aceita telefone sem parênteses se estiver
    # próximo de um rótulo TELEFONE/CELULAR/WHATSAPP.
    linhas = obter_linhas(
        texto
    )

    for i, linha in enumerate(linhas):

        n = normalizar_texto(
            linha
        )

        if not any(
            termo in n
            for termo in [
                "TELEFONE",
                "CELULAR",
                "WHATSAPP",
                "FONE"
            ]
        ):
            continue

        bloco = trecho_proximo(
            linhas,
            i,
            depois=2
        )

        numeros = re.findall(
            r"(?<!\d)"
            r"(?:55)?"
            r"(\d{2})"
            r"\s*"
            r"(9\d{4})"
            r"[\s.\-]*"
            r"(\d{4})"
            r"(?!\d)",
            bloco
        )

        if numeros:

            ddd, parte1, parte2 = (
                numeros[0]
            )

            return (
                f"({ddd}) "
                f"{parte1}-{parte2}"
            )

    return ""


# ============================================================
# ENDEREÇO
# ============================================================

def extrair_endereco(texto):
    resultado = {
        "endereco": "",
        "numero": "",
        "bairro": "",
        "cidade": ""
    }

    linhas = obter_linhas(
        texto
    )

    tipos = (
        r"(?:"
        r"RUA|"
        r"AVENIDA|"
        r"AV\.|"
        r"TRAVESSA|"
        r"RODOVIA|"
        r"ESTRADA|"
        r"PRACA|"
        r"PRAÇA|"
        r"ALAMEDA|"
        r"LOTEAMENTO|"
        r"CONJUNTO"
        r")"
    )

    for linha in linhas:

        n = normalizar_texto(
            linha
        )

        if not re.search(
            rf"\b{tipos}\b",
            n,
            re.I
        ):
            continue

        if any(
            termo in n
            for termo in [
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

        m = re.search(
            r"(?:,\s*|\bN[º°O]?\s*)"
            r"(\d+[A-Z]?)\b",
            linha_limpa,
            re.I
        )

        if m:

            resultado["numero"] = (
                m.group(1).upper()
            )

            resultado["endereco"] = (
                linha_limpa[
                    :m.start()
                ]
                .strip(" ,;-")
                .upper()
            )

            resto = (
                linha_limpa[
                    m.end():
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
                    resto.upper()
                )

        else:
            resultado["endereco"] = (
                linha_limpa.upper()
            )

        break

    return resultado


# ============================================================
# SEPARAÇÃO APROXIMADA
# ============================================================

def separar_blocos_documentos(texto):
    linhas = obter_linhas(
        texto
    )

    blocos = {
        "TITULO_ELEITORAL": [],
        "IDENTIDADE": [],
        "CNH": [],
        "COMPROVANTE_ENDERECO": [],
        "OUTROS": []
    }

    bloco_atual = "OUTROS"

    for linha in linhas:

        n = normalizar_texto(
            linha
        )

        if (
            "TITULO ELEITORAL" in n
            or "JUSTICA ELEITORAL" in n
        ):
            bloco_atual = (
                "TITULO_ELEITORAL"
            )

        elif (
            "CARTEIRA DE IDENTIDADE" in n
            or "REGISTRO GERAL" in n
            or "INSTITUTO DE IDENTIFICACAO" in n
        ):
            bloco_atual = (
                "IDENTIDADE"
            )

        elif (
            "CARTEIRA NACIONAL DE HABILITACAO"
            in n
        ):
            bloco_atual = "CNH"

        elif (
            "COMPROVANTE DE ENDERECO" in n
            or "COMPROVANTE DE RESIDENCIA" in n
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
    dados = resultado_vazio()

    documentos = identificar_documentos(
        texto
    )

    dados["nome"] = extrair_nome(
        texto
    )

    dados["cpf"] = extrair_cpf(
        texto
    )

    dados["rg"] = extrair_rg(
        texto
    )

    dados["data_nascimento"] = (
        extrair_data_nascimento(
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

    endereco = extrair_endereco(
        texto
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
# FUNÇÃO PRINCIPAL
# ============================================================

def analisar_documentos(texto):
    documentos = identificar_documentos(
        texto
    )

    blocos = separar_blocos_documentos(
        texto
    )

    dados = extrair_campos(
        texto
    )

    return {
        "documentos": documentos,
        "blocos": blocos,
        "dados": dados
    }
# ============================================================
# FUNÇÕES COMPLEMENTARES PARA CORREÇÃO DO NOME
# ============================================================

def extrair_nome_prioritario(texto):
    """
    Extrai o nome com prioridade máxima para o Título Eleitoral.
    Esta função é chamada quando o OCR principal falha.
    """
    return extrair_nome_titulo(texto)


def extrair_nome_mae_prioritario(texto, nome_pessoa=""):
    """
    Extrai o nome da mãe com prioridade para FILIAÇÃO no RG.
    """
    return extrair_nome_mae(texto, nome_pessoa)


def extrair_dados_completos_prioritario(texto):
    """
    Função principal que extrai dados priorizando Título Eleitoral e FILIAÇÃO.
    """
    return extrair_campos(texto)


# ============================================================
# FUNÇÕES DE FALLBACK PARA O APP.PY
# ============================================================

def extrair_nome_fallback(texto):
    """
    Fallback para extração de nome quando o OCR falha.
    Prioriza o Título Eleitoral.
    """
    return extrair_nome_titulo(texto)


def extrair_mae_fallback(texto, nome_pessoa=""):
    """
    Fallback para extração de nome da mãe quando o OCR falha.
    Prioriza FILIAÇÃO no RG.
    """
    return extrair_nome_mae(texto, nome_pessoa)


def extrair_tudo_fallback(texto):
    """
    Fallback completo para extração de todos os dados.
    """
    return extrair_campos(texto)


# ============================================================
# CORREÇÃO DE NOME ERRADO
# ============================================================

NOMES_ERRADOS_COMUNS = [
    "WILLAKS FÍRÂELRA DA SILVA",
    "WILLAKS FIRAELRA DA SILVA",
    "WILLAKS FÍRÂELRA",
    "WILLAKS FIRAELRA"
]


def nome_esta_errado(nome):
    """
    Verifica se o nome extraído está claramente errado.
    """
    nome = str(nome or "").strip().upper()
    if not nome:
        return True
    if nome in NOMES_ERRADOS_COMUNS:
        return True
    # Nomes muito curtos ou com caracteres estranhos
    if len(nome) < 5:
        return True
    # Se tiver muitos símbolos estranhos
    letras = re.sub(r"[^A-ZÀ-Ÿ]", "", nome)
    if len(letras) < 5:
        return True
    return False


def corrigir_nome_se_errado(nome, texto_original):
    """
    Se o nome estiver errado, tenta extrair novamente do texto.
    """
    if not nome_esta_errado(nome):
        return nome
    
    # Tenta extrair do Título Eleitoral
    nome_corrigido = extrair_nome_titulo(texto_original)
    if nome_corrigido and not nome_esta_errado(nome_corrigido):
        return nome_corrigido
    
    # Tenta extrair da Identidade
    nome_corrigido = extrair_nome_identidade(texto_original)
    if nome_corrigido and not nome_esta_errado(nome_corrigido):
        return nome_corrigido
    
    return nome
