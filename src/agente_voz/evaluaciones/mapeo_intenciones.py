from __future__ import annotations

# "fuera_de_alcance": ninguna de nuestras siete herramientas resuelve la intencion (por
# ejemplo, pedir un prestamo o abrir una cuenta conjunta). Se considera correcto si el
# agente no llama a ninguna herramienta o llama a derivar_a_humano (ver
# HERRAMIENTAS_ACEPTABLES_FUERA_DE_ALCANCE).
FUERA_DE_ALCANCE = "fuera_de_alcance"

# Mapeo revisado a mano contra ejemplos reales de transcripcion de cada clase (no es una
# traduccion literal del nombre en ingles). card_issues es el caso mas ambiguo: podria
# terminar en bloquear_tarjeta segun el motivo, pero la etiqueta no distingue eso.
MAPEO_INTENCION_A_HERRAMIENTA: dict[str, str] = {
    "freeze": "bloquear_tarjeta",
    "latest_transactions": "obtener_movimientos",
    "balance": "consultar_saldo",
    "abroad": "buscar_politicas",
    "atm_limit": "buscar_politicas",
    "cash_deposit": "buscar_politicas",
    "high_value_payment": "buscar_politicas",
    "address": FUERA_DE_ALCANCE,
    "app_error": FUERA_DE_ALCANCE,
    "business_loan": FUERA_DE_ALCANCE,
    "card_issues": FUERA_DE_ALCANCE,
    "direct_debit": FUERA_DE_ALCANCE,
    "joint_account": FUERA_DE_ALCANCE,
    "pay_bill": FUERA_DE_ALCANCE,
}

HERRAMIENTAS_ACEPTABLES_FUERA_DE_ALCANCE: frozenset[str | None] = frozenset(
    {None, "derivar_a_humano"}
)


def es_correcto(esperado: str, obtenido: str | None) -> bool:
    if esperado == FUERA_DE_ALCANCE:
        return obtenido in HERRAMIENTAS_ACEPTABLES_FUERA_DE_ALCANCE
    return obtenido == esperado
