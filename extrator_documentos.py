import re
import unicodedata
from datetime import datetime


# ============================================================
# UTILIDADES
# ============================================================

def limpar_texto(valor):
    if valor is None:
        return ""
    return re.sub(r"\s+", " ", str(valor)).strip()


def sem_acentos(valor):
    valor = limpar_texto(valor)

    return "".join(
        c for c in unicodedata.normalize("NFD", valor)
        if unicodedata.category(c) != "Mn"
    ).upper()


def somente_numeros(valor):
    return re.sub(r"\D", "", limpar_texto(valor))


def texto(bloco):
    """
    IMPORTANTE:
    Agora o extrator recebe os dicionários criados
    pelo teste_ocr.py.
    """
    if isinstance(bloco, dict):
        return limpar_texto(bloco.get("texto", ""))

    return limpar_texto(bloco)


def confianca(bloco):
    if not isinstance(bloco, dict):
        return 0.0

    try:
        return float(bloco.get("confianca") or 0)
    except Exception:
        return 0.0


# ============================================================
# NORMALIZAÇÃO PARA COMPARAR RÓTULOS
# ============================================================

def compacto(valor):
    return re.sub(
        r"[^A-Z0-9]",
        "",
        sem_acentos(valor)
    )


def contem_algum(valor, termos):
    normal = sem_acentos(valor)
    comp = compacto(valor)

    for termo in termos:
        termo_normal = sem_acentos(termo)
        termo_comp = compacto(termo)

        if termo_normal in normal:
            return True

        if len(termo_comp) >= 5 and termo_comp in comp:
            return True

    return False


# ============================================================
# CPF
# ============================================================

def cpf_valido(numero):
    numero = somente_numeros(numero)

    if len(numero) != 11:
        return False

    if numero == numero[0] * 11:
        return False

    try:
        soma = sum(
            int(numero[i]) * (10 - i)
            for i in range(9)
        )

        resto = soma % 11
        d1 = 0 if resto < 2 else 11 - resto

        soma = sum(
            int(numero[i]) * (11 - i)
            for i in range(10)
        )

        resto = soma % 11
        d2 = 0 if resto < 2 else 11 - resto

        return numero[-2:] == f"{d1}{d2}"

    except Exception:
        return False


def formatar_cpf(numero):
    numero = somente_numeros(numero)

    return (
        f"{numero[:3]}."
        f"{numero[3:6]}."
        f"{numero[6:9]}-"
        f"{numero[9:]}"
    )


def extrair_cpf(blocos):
    # Primeiro: CPF matematicamente válido.
    for bloco in blocos:
        numero = somente_numeros(texto(bloco))

        if len(numero) == 11 and cpf_valido(numero):
            return formatar_cpf(numero)

    # Segundo: número de 11 dígitos explicitamente
    # associado a CPF.
    for i, bloco in enumerate(blocos):
        if not contem_algum(texto(bloco), ["CPF"]):
            continue

        for j in range(i, min(i + 4, len(blocos))):
            numero = somente_numeros(texto(blocos[j]))

            if len(numero) == 11:
                return formatar_cpf(numero)

    return ""


# ============================================================
# DATA DE NASCIMENTO
# ============================================================

PADRAO_DATA = re.compile(
    r"\b"
    r"(0?[1-9]|[12]\d|3[01])"
    r"[\/\-.]"
    r"(0?[1-9]|1[0-2])"
    r"[\/\-.]"
    r"((?:19|20)\d{2})"
    r"\b"
)


def extrair_datas(valor):
    encontrados = []

    for match in PADRAO_DATA.finditer(texto(valor)):
        dia = int(match.group(1))
        mes = int(match.group(2))
        ano = int(match.group(3))

        try:
            data = datetime(ano, mes, dia)
            encontrados.append(data)
        except ValueError:
            pass

    return encontrados


def extrair_nascimento(blocos):
    candidatos = []

    ano_atual = datetime.now().year

    for indice, bloco in enumerate(blocos):
        for data in extrair_datas(bloco):

            pontos = 0

            idade = ano_atual - data.year

            # Cadastro de adulto: forte indício.
            if 16 <= idade <= 110:
                pontos += 40
            elif 0 <= idade <= 110:
                pontos += 10

            # Confiança do OCR.
            pontos += confianca(bloco) * 10

            # Procura contexto próximo na ORDEM do OCR.
            inicio = max(0, indice - 4)
            fim = min(len(blocos), indice + 5)

            contexto = " ".join(
                sem_acentos(texto(b))
                for b in blocos[inicio:fim]
            )

            if any(
                marcador in contexto
                for marcador in [
                    "NASCIMENTO",
                    "NASC",
                    "NASCIME",
                    "DATA DE NASC"
                ]
            ):
                pontos += 60

            if any(
                marcador in contexto
                for marcador in [
                    "EMISSAO",
                    "VALIDADE",
                    "EXPEDICAO"
                ]
            ):
                pontos -= 30

            candidatos.append(
                (pontos, data)
            )

    if not candidatos:
        return ""

    candidatos.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return candidatos[0][1].strftime("%d/%m/%Y")


# ============================================================
# TÍTULO ELEITORAL
# ============================================================

def extrair_titulo(blocos):
    candidatos = []

    for indice, bloco in enumerate(blocos):
        valor = texto(bloco)
        numero = somente_numeros(valor)

        if len(numero) != 12:
            continue

        pontos = 20

        # Título frequentemente aparece agrupado:
        # 0417 1503 1791
        if len(valor.split()) >= 2:
            pontos += 15

        inicio = max(0, indice - 12)
        fim = min(len(blocos), indice + 5)

        contexto = " ".join(
            sem_acentos(texto(b))
            for b in blocos[inicio:fim]
        )

        # Aceita inclusive OCR ruim como
        # TITULOFLFITORAL.
        if "TITULO" in contexto:
            pontos += 70

        if "ELEITOR" in contexto:
            pontos += 30

        pontos += confianca(bloco) * 10

        candidatos.append(
            (pontos, numero, indice)
        )

    if not candidatos:
        return "", None

    candidatos.sort(
        key=lambda item: item[0],
        reverse=True
    )

    melhor = candidatos[0]

    return melhor[1], melhor[2]


# ============================================================
# NOME
# ============================================================

def parece_nome(valor):
    valor = limpar_texto(valor)

    if len(valor) < 7:
        return False

    if any(c.isdigit() for c in valor):
        return False

    letras = sum(c.isalpha() for c in valor)

    if letras < 7:
        return False

    normal = sem_acentos(valor)

    proibidos = [
        "REPUBLICA",
        "FEDERATIVA",
        "SECRETARIA",
        "SEGURANCA",
        "PUBLICA",
        "IDENTIFICACAO",
        "BIOMETRICA",
        "ELEITORAL",
        "TITULO",
        "CARTEIRA",
        "IDENTIDADE",
        "HABILITACAO",
        "NASCIMENTO",
        "VALIDADE",
        "EMISSAO",
        "ASSINATURA",
        "MUNICIPIO",
        "REGISTRO",
        "BRASIL",
        "ESTADO"
    ]

    if any(p in normal for p in proibidos):
        return False

    return True


def extrair_nome(blocos):
    candidatos = []

    for indice, bloco in enumerate(blocos):
        valor = texto(bloco)

        if not parece_nome(valor):
            continue

        pontos = confianca(bloco) * 20

        inicio = max(0, indice - 5)
        fim = min(len(blocos), indice + 3)

        contexto = " ".join(
            sem_acentos(texto(b))
            for b in blocos[inicio:fim]
        )

        if "NOME" in contexto:
            pontos += 60

        if "ELEITOR" in contexto:
            pontos += 30

        # Nome localizado dentro de região reconhecida
        # como título/identidade recebe reforço.
        if (
            "IDENTIFICACAO" in contexto
            or "BIOMETRICA" in contexto
        ):
            pontos += 20

        candidatos.append(
            (pontos, valor.upper())
        )

    if not candidatos:
        return ""

    candidatos.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return candidatos[0][1]


# ============================================================
# TELEFONE
# ============================================================

def formatar_telefone(numero):
    numero = somente_numeros(numero)
    if len(numero) == 11:
        return f"({numero[:2]}) {numero[2:7]}-{numero[7:]}"
    if len(numero) == 10:
        return f"({numero[:2]}) {numero[2:6]}-{numero[6:]}"
    if len(numero) == 9:
        return f"{numero[:5]}-{numero[5:]}"
    if len(numero) == 8:
        return f"{numero[:4]}-{numero[4:]}"
    return numero


def extrair_telefone(blocos, cpf, titulo):
    cpf_num = somente_numeros(cpf)
    titulo_num = somente_numeros(titulo)
    candidatos = []

    def adicionar(numero, valor, indice, bonus=0):
        if len(numero) not in (8, 9, 10, 11):
            return
        if numero in {cpf_num, titulo_num, ""}:
            return
        if len(numero) == 11 and cpf_valido(numero):
            return

        if len(numero) == 8:
            try:
                datetime.strptime(numero, "%d%m%Y")
                return
            except ValueError:
                pass

        inicio = max(0, indice - 4)
        fim = min(len(blocos), indice + 5)
        contexto = " ".join(sem_acentos(texto(b)) for b in blocos[inicio:fim])
        rotulo = any(t in contexto for t in
                     ["TELEFONE", "CELULAR", "FONE", "CONTATO", "WHATS"])

        pontos = confianca(blocos[indice]) * 10 + bonus
        if rotulo:
            pontos += 100
        if "-" in valor:
            pontos += 30
        if "(" in valor or ")" in valor:
            pontos += 25

        if len(numero) == 11 and numero[2] == "9":
            pontos += 65
        elif len(numero) == 10 and numero[2] in "2345":
            pontos += 30
        elif len(numero) == 9 and numero[0] == "9":
            pontos += 70
        elif len(numero) == 8 and numero[0] in "2345":
            pontos += 20
        else:
            pontos -= 40

        if any(t in contexto for t in [
            "CEP", "MATRICULA", "HIDROMETRO", "CONSUMO", "FATURA",
            "INSCRICAO", "CPF", "TITULO", "ZONA", "SECAO",
            "REGISTRO", "IDENTIDADE", "NASCIMENTO", "EMISSAO",
            "VALIDADE", "CNS", "CTPS"
        ]) and not rotulo:
            pontos -= 45

        if len(set(numero)) <= 3:
            pontos -= 30

        candidatos.append((pontos, numero))

    for i, bloco in enumerate(blocos):
        valor = texto(bloco)
        adicionar(somente_numeros(valor), valor, i)

    # Telefones manuscritos às vezes são quebrados em 2 ou 3 blocos.
    for i in range(len(blocos)):
        partes = []
        for j in range(i, min(i + 3, len(blocos))):
            bruto = texto(blocos[j])
            nums = somente_numeros(bruto)
            if not nums or len(nums) > 7:
                break

            if j > i:
                try:
                    a = blocos[j - 1]
                    b = blocos[j]
                    if a.get("pagina") != b.get("pagina"):
                        break
                    dx = abs(float(b["x_relativo"]) - float(a["x_relativo"]))
                    dy = abs(float(b["y_relativo"]) - float(a["y_relativo"]))
                    if dx > 0.18 or dy > 0.08:
                        break
                except Exception:
                    pass

            partes.append(nums)
            combinado = "".join(partes)
            if len(combinado) in (8, 9, 10, 11):
                valor_combinado = " ".join(texto(blocos[k]) for k in range(i, j + 1))
                adicionar(combinado, valor_combinado, i, bonus=20)

    if not candidatos:
        return ""

    candidatos.sort(key=lambda item: item[0], reverse=True)
    pontos, numero = candidatos[0]

    if pontos < 60:
        return ""

    return formatar_telefone(numero)


# ============================================================
# ZONA / SEÇÃO
# ============================================================

def extrair_zona_secao(blocos, indice_titulo):
    """
    Extrai ZONA e SEÇÃO sem depender de layout fixo.

    Estratégia:
    1) procura os rótulos ZONA e SEÇÃO em toda a página;
    2) aceita o número imediatamente antes OU depois do rótulo;
    3) dá preferência aos candidatos próximos ao TÍTULO ELEITORAL;
    4) evita confundir data, CPF, título e números longos.
    """

    def numero_curto(indice, max_digitos):
        if indice < 0 or indice >= len(blocos):
            return None

        valor = somente_numeros(texto(blocos[indice]))

        if not valor:
            return None

        if not (1 <= len(valor) <= max_digitos):
            return None

        return valor

    def distancia_titulo(indice):
        if indice_titulo is None:
            return 999
        return abs(indice - indice_titulo)

    zona_candidatos = []
    secao_candidatos = []

    # --------------------------------------------------------
    # 1) RÓTULOS EXPLÍCITOS
    # --------------------------------------------------------

    for indice, bloco in enumerate(blocos):
        normal = sem_acentos(texto(bloco))
        comp = compacto(texto(bloco))

        eh_zona = (
            normal == "ZONA"
            or "ZONA" in normal
            or comp == "ZONA"
        )

        eh_secao = (
            normal == "SECAO"
            or "SECAO" in normal
            or comp == "SECAO"
        )

        if eh_zona:
            # OCR pode devolver o valor antes ou depois do rótulo.
            for deslocamento in [-1, 1, -2, 2, -3, 3, -4, 4]:
                j = indice + deslocamento
                numero = numero_curto(j, 3)

                if numero is None:
                    continue

                pontos = 100
                pontos -= abs(deslocamento) * 8
                pontos -= distancia_titulo(j) * 2
                pontos += confianca(blocos[j]) * 10

                zona_candidatos.append(
                    (pontos, j, numero)
                )

        if eh_secao:
            for deslocamento in [-1, 1, -2, 2, -3, 3, -4, 4]:
                j = indice + deslocamento
                numero = numero_curto(j, 4)

                if numero is None:
                    continue

                pontos = 100
                pontos -= abs(deslocamento) * 8
                pontos -= distancia_titulo(j) * 2
                pontos += confianca(blocos[j]) * 10

                secao_candidatos.append(
                    (pontos, j, numero)
                )

    # --------------------------------------------------------
    # 2) FALLBACK: REGIÃO DO TÍTULO
    # --------------------------------------------------------
    # Em vários títulos o OCR reconhece:
    #
    # TITULO ...
    # nascimento
    # número do título
    # zona
    # seção
    #
    # mas pode falhar justamente nos rótulos.
    # Por isso analisamos números curtos perto do título.
    # --------------------------------------------------------

    if indice_titulo is not None:

        inicio = max(0, indice_titulo - 6)
        fim = min(len(blocos), indice_titulo + 10)

        curtos = []

        for j in range(inicio, fim):
            if j == indice_titulo:
                continue

            valor_original = texto(blocos[j])
            numero = somente_numeros(valor_original)

            if not numero:
                continue

            # Ignora datas e números longos.
            if "/" in valor_original:
                continue

            if 1 <= len(numero) <= 4:
                curtos.append(
                    (
                        j,
                        numero,
                        abs(j - indice_titulo),
                        confianca(blocos[j])
                    )
                )

        # Zona normalmente tem até 3 dígitos.
        if not zona_candidatos:
            for j, numero, distancia, conf in curtos:
                if len(numero) <= 3:
                    pontos = 40
                    pontos -= distancia * 3
                    pontos += conf * 10

                    zona_candidatos.append(
                        (pontos, j, numero)
                    )

        # Seção normalmente tem até 4 dígitos.
        if not secao_candidatos:
            for j, numero, distancia, conf in curtos:
                if len(numero) <= 4:
                    pontos = 35
                    pontos -= distancia * 3
                    pontos += conf * 10

                    secao_candidatos.append(
                        (pontos, j, numero)
                    )

    # --------------------------------------------------------
    # ESCOLHER MELHORES
    # --------------------------------------------------------

    zona = ""
    secao = ""
    indice_zona = None

    if zona_candidatos:
        zona_candidatos.sort(
            key=lambda item: item[0],
            reverse=True
        )

        _, indice_zona, zona = zona_candidatos[0]

    if secao_candidatos:
        # Evita usar exatamente o mesmo bloco escolhido como zona,
        # quando houver outro candidato plausível para seção.
        diferentes = [
            item
            for item in secao_candidatos
            if item[1] != indice_zona
        ]

        lista = (
            diferentes
            if diferentes
            else secao_candidatos
        )

        lista.sort(
            key=lambda item: item[0],
            reverse=True
        )

        _, _, secao = lista[0]

    # Mantém zeros à esquerda para a planilha.
    if zona:
        zona = zona.zfill(3)

    if secao:
        secao = secao.zfill(4)

    return zona, secao


# ============================================================
# RG
# ============================================================

def extrair_rg(blocos, cpf, titulo):
    proibidos = {
        somente_numeros(cpf),
        somente_numeros(titulo),
        ""
    }

    candidatos = []

    for indice, bloco in enumerate(blocos):
        valor = texto(bloco)
        numero = somente_numeros(valor)

        if not (6 <= len(numero) <= 10):
            continue

        if numero in proibidos:
            continue

        if len(numero) == 8:
            try:
                datetime.strptime(numero, "%d%m%Y")
                continue
            except ValueError:
                pass

        pontos = confianca(bloco) * 15

        inicio = max(0, indice - 8)
        fim = min(len(blocos), indice + 9)

        contexto = " ".join(
            sem_acentos(texto(b))
            for b in blocos[inicio:fim]
        )

        if "DOC IDENTIDADE" in contexto:
            pontos += 120

        if "REGISTRO GERAL" in contexto:
            pontos += 110

        if re.search(r"RG", contexto):
            pontos += 100

        if "IDENTIDADE" in contexto:
            pontos += 45

        if any(
            termo in contexto
            for termo in [
                "SSP",
                "SCJDS",
                "ORGAO EXPEDIDOR",
                "ORG EXPEDIDOR",
                "EXPEDIDOR"
            ]
        ):
            pontos += 45

        if 7 <= len(numero) <= 9:
            pontos += 25

        normal_valor = sem_acentos(valor)

        # Ex.: "31213766 SCJDS AL"
        if "SSP" in normal_valor or "SCJDS" in normal_valor:
            pontos += 80

        if any(
            termo in contexto
            for termo in [
                "CEP",
                "TELEFONE",
                "CELULAR",
                "FONE",
                "MATRICULA",
                "HIDROMETRO",
                "CONSUMO",
                "FATURA"
            ]
        ):
            pontos -= 50

        candidatos.append(
            (pontos, numero)
        )

    if not candidatos:
        return ""

    candidatos.sort(
        key=lambda item: item[0],
        reverse=True
    )

    if candidatos[0][0] < 55:
        return ""

    return candidatos[0][1]


# ============================================================
# NOME DA MÃE
# ============================================================

def _nome_filiacao_valido(valor, nome_principal):
    valor = limpar_texto(valor)
    if not parece_nome(valor):
        return False

    normal = sem_acentos(valor)
    if nome_principal and normal == sem_acentos(nome_principal):
        return False

    proibidos = [
        "RESPONSAVEL", "CLIENTE", "CPF", "CNPJ", "ENDERECO",
        "COMPANHIA", "SANEAMENTO", "CASAL", "FATURA", "CONSUMO",
        "VENCIMENTO", "MATRICULA", "HIDROMETRO", "ASSINATURA",
        "PORTADOR", "NACIONALIDADE", "VALIDADE", "NASCIMENTO",
        "IDENTIDADE", "REGISTRO", "ELEITORAL", "SECRETARIA",
        "REPUBLICA", "BRASILEIRO", "ORGAO", "EXPEDIDOR"
    ]
    if any(termo in normal for termo in proibidos):
        return False

    palavras = re.findall(r"[A-ZÀ-Ú]+", normal)
    return len(palavras) >= 2


def extrair_nome_mae(blocos, nome):
    # Primeiro procura NOME DA MÃE / MÃE.
    for indice, bloco in enumerate(blocos):
        normal = sem_acentos(texto(bloco))
        comp = compacto(texto(bloco))

        if not ("NOME DA MAE" in normal or "NOMEDAMAE" in comp or normal == "MAE"):
            continue

        for j in range(indice + 1, min(indice + 12, len(blocos))):
            candidato = texto(blocos[j])
            if _nome_filiacao_valido(candidato, nome):
                return candidato.upper()

    # Depois usa FILIAÇÃO sem depender de coordenada fixa.
    for indice, bloco in enumerate(blocos):
        comp = compacto(texto(bloco))
        if "FILIACAO" not in comp and "FILIACA" not in comp:
            continue

        nomes = []

        for j in range(indice + 1, min(indice + 22, len(blocos))):
            candidato = texto(blocos[j])
            normal = sem_acentos(candidato)

            if nomes and any(t in normal for t in [
                "ASSINATURA", "TITULO ELEITORAL", "NOME DO ELEITOR",
                "CPF/CNPJ", "ENDERECO DE ENTREGA", "OBSERVACOES"
            ]):
                break

            if not _nome_filiacao_valido(candidato, nome):
                continue

            candidato = candidato.upper()
            if sem_acentos(candidato) not in [sem_acentos(x) for x in nomes]:
                nomes.append(candidato)

            # Em CNH/RG, normalmente pai e mãe vêm nessa ordem.
            if len(nomes) >= 2:
                return nomes[1]

    return ""


# ============================================================
# ENDEREÇO
# ============================================================

def extrair_endereco(blocos):
    tipos = [
        "RUA ",
        "AVENIDA ",
        "AV ",
        "TRAVESSA ",
        "TV ",
        "RODOVIA ",
        "ESTRADA ",
        "SITIO ",
        "POVOADO ",
        "LOTEAMENTO ",
        "RESIDENCIAL ",
        "CONJUNTO ",
        "PRACA "
    ]

    for bloco in blocos:
        valor = texto(bloco)
        normal = sem_acentos(valor)

        if any(
            normal.startswith(tipo)
            for tipo in tipos
        ):
            return valor.upper()

    return ""


# ============================================================
# CIDADE
# ============================================================

def extrair_cidade(blocos):
    for bloco in blocos:
        valor = texto(bloco)
        normal = sem_acentos(valor)

        # Exemplos:
        # ARAPIRACA/AL
        # ARAPIRACA-AL
        match = re.search(
            r"\b([A-ZÀ-Ú][A-ZÀ-Ú\s]{2,})"
            r"[\-/]"
            r"([A-Z]{2})\b",
            valor.upper()
        )

        if match:
            cidade = limpar_texto(
                match.group(1)
            )

            if cidade:
                return cidade.upper()

        # OCR pode colar:
        # ARAPIRACAVAL
        if normal.endswith("AL") and len(normal) > 4:
            candidato = re.sub(
                r"[^A-Z]",
                "",
                normal
            )

            if candidato.endswith("AL"):
                candidato = candidato[:-2]

                # Evita palavras aleatórias.
                if len(candidato) >= 4:
                    return candidato

    return ""


# ============================================================
# EXTRATOR PRINCIPAL
# ============================================================


# ============================================================
# LEITURA POR RÓTULOS EXPLÍCITOS
# ============================================================

def _distancia(a, b):
    try:
        ax, ay = float(a["x_relativo"]), float(a["y_relativo"])
        bx, by = float(b["x_relativo"]), float(b["y_relativo"])
        return ((ax-bx)**2 + (ay-by)**2) ** 0.5
    except Exception:
        return 999.0


def _eh_rotulo(valor):
    n = sem_acentos(valor)
    c = compacto(valor)
    termos = [
        "NOME DO ELEITOR", "NOMEDOELEITOR", "DATA DE NASCIMENTO",
        "DATADENASCIMENTO", "INSCRICAO", "ZONA", "SECAO", "MUNICIPIO",
        "FILIACAO", "CODIGO DE VALIDACAO", "CODIGODEVALIDACAO",
        "DATA DE EMISSAO", "JUSTICA ELEITORAL", "REPUBLICA FEDERATIVA",
        "TITULO ELEITORAL"
    ]
    return any(t in n or t in c for t in termos)


def _nome_forte(valor):
    valor = limpar_texto(valor)
    if not parece_nome(valor) or _eh_rotulo(valor):
        return False
    n = sem_acentos(valor)
    proibidos = [
        "CODIGO", "VALIDACAO", "JUSTICA", "ELEITORAL", "REPUBLICA",
        "FEDERATIVA", "BRASIL", "ORIENTACOES", "TRIBUNAL", "INTERNET",
        "MUNICIPIO", "BIOMETRIA", "ELEITOR", "ELEITORA", "TITULO"
    ]
    return not any(p in n for p in proibidos)


def _perto(blocos, i, limite):
    r = blocos[i]
    itens = []
    for j, b in enumerate(blocos):
        if j == i or b.get("pagina") != r.get("pagina"):
            continue
        d = _distancia(r, b)
        if d <= limite:
            itens.append((d, j, b))
    return sorted(itens, key=lambda x: x[0])


def extrair_nome_rotulado(blocos):
    for i, b in enumerate(blocos):
        n, c = sem_acentos(texto(b)), compacto(texto(b))
        if "NOME DO ELEITOR" not in n and "NOMEDOELEITOR" not in c:
            continue
        candidatos = []
        for d, _, cand in _perto(blocos, i, 0.16):
            v = limpar_texto(texto(cand))
            if _nome_forte(v):
                candidatos.append((100 - d*200, v.upper()))
        if candidatos:
            return max(candidatos)[1]
    return ""


def extrair_cidade_rotulada(blocos):
    for i, b in enumerate(blocos):
        n = sem_acentos(texto(b))
        if "MUNICIPIO" not in n:
            continue
        candidatos = []
        for d, _, cand in _perto(blocos, i, 0.15):
            v = limpar_texto(texto(cand)).upper()
            vn = sem_acentos(v)
            if _eh_rotulo(v) or any(x in vn for x in ["CODIGO","VALIDACAO","JUSTICA","ELEITORAL"]):
                continue
            m = re.match(r"^\s*([A-ZÀ-Ú][A-ZÀ-Ú\s.'-]{2,}?)(?:\s*[/\-]\s*[A-Z]{2})?\s*$", v)
            if m:
                cidade = limpar_texto(m.group(1)).strip(" -/")
                if len(cidade) >= 3:
                    candidatos.append((100-d*200, cidade))
        if candidatos:
            return max(candidatos)[1]
    return ""


def extrair_zona_secao_rotuladas(blocos):
    saida = {"ZONA": "", "SEÇÃO": ""}
    for chave, termo in [("ZONA","ZONA"), ("SEÇÃO","SECAO")]:
        melhores = []
        for i, b in enumerate(blocos):
            if termo not in sem_acentos(texto(b)):
                continue
            for d, _, cand in _perto(blocos, i, 0.09):
                bruto = limpar_texto(texto(cand))
                num = somente_numeros(bruto)
                if not num or len(num) > 4:
                    continue
                # bloco deve ser essencialmente numérico
                if len(num) < max(1, len(bruto.replace(" ","")) - 1):
                    continue
                pontos = 100-d*300
                try:
                    dx = abs(float(cand["x_relativo"])-float(b["x_relativo"]))
                    if dx < 0.055:
                        pontos += 35
                except Exception:
                    pass
                melhores.append((pontos, num))
        if melhores:
            valor = max(melhores)[1]
            saida[chave] = valor.zfill(3 if chave=="ZONA" else 4)
    return saida["ZONA"], saida["SEÇÃO"]


def extrair_mae_filiacao_rotulada(blocos, nome_principal):
    for i, b in enumerate(blocos):
        c = compacto(texto(b))
        if "FILIACAO" not in c and "FILIACA" not in c:
            continue

        candidatos = []
        for d, j, cand in _perto(blocos, i, 0.20):
            v = limpar_texto(texto(cand))
            if not _nome_filiacao_valido(v, nome_principal):
                continue
            try:
                y = float(cand["y_relativo"])
                x = float(cand["x_relativo"])
            except Exception:
                y, x = 9.0, 9.0
            candidatos.append((y, x, d, v.upper()))

        if candidatos:
            # Título eleitoral não informa "pai/mãe"; no modelo testado,
            # o primeiro nome visual da filiação é a mãe.
            candidatos.sort(key=lambda z: (z[0], z[1]))
            return candidatos[0][3]
    return ""


def extrair_dados(blocos, recuperados=None):

    # Segurança: garante que estamos usando a versão correta.
    if blocos and not isinstance(blocos[0], dict):
        raise TypeError(
            "O extrator V2 esperava blocos do RapidOCR, "
            "mas recebeu textos simples."
        )

    nome = extrair_nome(blocos)

    cpf = extrair_cpf(blocos)

    nascimento = extrair_nascimento(
        blocos
    )

    titulo, indice_titulo = extrair_titulo(
        blocos
    )

    zona, secao = extrair_zona_secao(
        blocos,
        indice_titulo
    )

    rg = extrair_rg(
        blocos,
        cpf,
        titulo
    )

    nome_mae = extrair_nome_mae(
        blocos,
        nome
    )

    telefone = extrair_telefone(
        blocos,
        cpf,
        titulo
    )

    endereco = extrair_endereco(
        blocos
    )

    cidade = extrair_cidade(
        blocos
    )

    # Rótulos explícitos têm prioridade sobre heurísticas genéricas.
    nome_rotulo = extrair_nome_rotulado(blocos)
    if nome_rotulo:
        nome = nome_rotulo

    cidade_rotulo = extrair_cidade_rotulada(blocos)
    if cidade_rotulo:
        cidade = cidade_rotulo

    zona_rotulo, secao_rotulo = extrair_zona_secao_rotuladas(blocos)
    if zona_rotulo:
        zona = zona_rotulo
    if secao_rotulo:
        secao = secao_rotulo

    mae_rotulo = extrair_mae_filiacao_rotulada(blocos, nome)
    if mae_rotulo:
        nome_mae = mae_rotulo

    recuperados = recuperados or {}

    mae_recuperada = limpar_texto(
        recuperados.get("NOME DA MÃE", "")
    )
    telefone_recuperado = limpar_texto(
        recuperados.get("TELEFONE", "")
    )

    if mae_recuperada:
        nome_mae = mae_recuperada.upper()

    if telefone_recuperado:
        telefone = telefone_recuperado

    return {
        "NOME": nome,
        "CPF": cpf,
        "RG": rg,
        "DATA DE NASCIMENTO": nascimento,
        "NOME DA MÃE": nome_mae,

        "ENDEREÇO": endereco,
        "Nº": "",
        "BAIRRO": "",
        "CIDADE": cidade,

        "TITULO": titulo,
        "ZONA": zona,
        "SEÇÃO": secao,

        "TELEFONE": telefone
    }


# ============================================================
# MOSTRAR RESULTADO
# ============================================================

def mostrar_dados(dados):

    print()
    print("=" * 70)
    print("DADOS EXTRAÍDOS")
    print("=" * 70)

    ordem = [
        "NOME",
        "CPF",
        "RG",
        "DATA DE NASCIMENTO",
        "NOME DA MÃE",
        "ENDEREÇO",
        "Nº",
        "BAIRRO",
        "CIDADE",
        "TITULO",
        "ZONA",
        "SEÇÃO",
        "TELEFONE"
    ]

    for campo in ordem:
        valor = dados.get(campo, "")

        if not valor:
            valor = "NÃO ENCONTRADO"

        print(
            f"{campo:<20}: {valor}"
        )

    print("=" * 70)

# ============================================================
# COMPATIBILIDADE COM leitor_documentos.py
# ============================================================

def analisar_documentos(texto_bruto):
    linhas = [x.strip() for x in str(texto_bruto or "").splitlines() if x.strip()]
    blocos = [
        {
            "texto": linha, "confianca": 1.0, "pagina": 1,
            "largura_pagina": 1, "altura_pagina": 1,
            "box": None, "x_min": None, "y_min": None,
            "x_max": None, "y_max": None, "centro_x": None,
            "centro_y": None, "x_relativo": None, "y_relativo": None,
        }
        for linha in linhas
    ]
    return extrair_dados(blocos) if blocos else {}
