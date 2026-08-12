import cruzamento


# ============================================================
# TESTE DO CRUZAMENTO
# ============================================================

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyjYTHwcHgMAT3LDKxHPX2rvZO5X8jORdWBvh4nbSvhqLtV3TwSAnCIiI9gNaSds-Ru/exec"


titulo_teste = "42520321708"


resultado = cruzamento.consultar_titulo(
    WEBHOOK_URL,
    titulo_teste
)


print("=" * 60)
print("TESTE DE CRUZAMENTO")
print("=" * 60)

print(
    "Título:",
    resultado["titulo"]
)

print(
    "Consulta funcionou:",
    resultado["sucesso"]
)

print(
    "Encontrado:",
    resultado["encontrado"]
)

print(
    "Bases:",
    resultado["bases"]
)

print(
    "Texto:",
    resultado["texto"]
)

print(
    "Mensagem:",
    resultado["mensagem"]
)
