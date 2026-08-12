import re
import unicodedata
from datetime import datetime


# ============================================================
# FUNÇÕES BÁSICAS / VALIDAÇÕES
# ============================================================

def somente_numeros(valor):
    return re.sub(
        r"\D",
        "",
        str(valor or "")
    )


def normalizar_texto(valor):
    return str(
        valor or ""
    ).strip().upper()


def remover_acentos(valor):
    valor = str(
        valor or ""
    )

    return "".join(
        caractere
        for caractere in unicodedata.normalize(
            "NFD",
            valor
        )
        if unicodedata.category(
            caractere
        ) != "Mn"
    )


def normalizar_rotulo(valor):
    valor = remover_acentos(
        valor
    ).upper()

    return re.sub(
        r"[^A-Z0-9]",
        "",
        valor
    )


def formatar_cpf(cpf):
    cpf = somente_numeros(
        cpf
    )

    if len(cpf) != 11:
        return cpf

    return (
        f"{cpf[0:3]}."
        f"{cpf[3:6]}."
        f"{cpf[6:9]}-"
        f"{cpf[9:11]}"
    )


def cpf_valido(cpf):
    """
    Valida CPF pelos dígitos verificadores.
    Não infere nem corrige números.
    """

    cpf = somente_numeros(
        cpf
    )

    if (
        len(cpf) != 11
        or cpf == cpf[0] * 11
    ):
        return False

    for tamanho in (9, 10):

        soma = sum(
            int(cpf[i])
            * (tamanho + 1 - i)
            for i in range(tamanho)
        )

        digito = (
            soma * 10
        ) % 11

        if digito == 10:
            digito = 0

        if digito != int(
            cpf[tamanho]
        ):
            return False

    return True


def data_valida(valor):
    """
    Valida uma data real nos formatos:

    DD/MM/AAAA
    DD-MM-AAAA
    DD.MM.AAAA
    """

    valor = str(
        valor or ""
    ).strip()

    match = re.fullmatch(
        r"(\d{2})[\/.\-](\d{2})[\/.\-](\d{4})",
        valor
    )

    if not match:
        return False

    try:
        datetime.strptime(
            (
                f"{match.group(1)}/"
                f"{match.group(2)}/"
                f"{match.group(3)}"
            ),
            "%d/%m/%Y"
        )

        return (
            1900
            <= int(match.group(3))
            <= datetime.now().year
        )

    except ValueError:
        return False
