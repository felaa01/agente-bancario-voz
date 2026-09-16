from __future__ import annotations

from agente_voz.evaluaciones.dataset_intenciones import NOMBRES_INTENCIONES
from agente_voz.evaluaciones.mapeo_intenciones import (
    FUERA_DE_ALCANCE,
    MAPEO_INTENCION_A_HERRAMIENTA,
    es_correcto,
)

_NOMBRES_DE_HERRAMIENTAS = {
    "verificar_identidad",
    "consultar_saldo",
    "obtener_movimientos",
    "bloquear_tarjeta",
    "abrir_disputa",
    "buscar_politicas",
    "derivar_a_humano",
}


def prueba_el_mapeo_cubre_las_14_intenciones_del_dataset() -> None:
    assert set(MAPEO_INTENCION_A_HERRAMIENTA) == set(NOMBRES_INTENCIONES)


def prueba_cada_valor_del_mapeo_es_una_herramienta_real_o_fuera_de_alcance() -> None:
    valores = set(MAPEO_INTENCION_A_HERRAMIENTA.values())
    assert valores <= _NOMBRES_DE_HERRAMIENTAS | {FUERA_DE_ALCANCE}


def prueba_es_correcto_para_una_herramienta_especifica() -> None:
    assert es_correcto("bloquear_tarjeta", "bloquear_tarjeta")
    assert not es_correcto("bloquear_tarjeta", "obtener_movimientos")
    assert not es_correcto("bloquear_tarjeta", None)


def prueba_es_correcto_para_fuera_de_alcance() -> None:
    assert es_correcto(FUERA_DE_ALCANCE, None)
    assert es_correcto(FUERA_DE_ALCANCE, "derivar_a_humano")
    assert not es_correcto(FUERA_DE_ALCANCE, "bloquear_tarjeta")
