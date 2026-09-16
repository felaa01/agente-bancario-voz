from __future__ import annotations

from pathlib import Path

from agente_voz.evaluaciones.dataset_intenciones import (
    RUTA_MUESTRA_POR_DEFECTO,
    EjemploIntencion,
    cargar_dataset,
    guardar_dataset,
    muestrear_estratificado,
)


def prueba_guardar_y_cargar_es_identico(tmp_path: Path) -> None:
    ejemplos: list[EjemploIntencion] = [
        {"transcripcion": "quiero ver mi saldo", "intencion": "balance"},
        {"transcripcion": "bloqueenme la tarjeta", "intencion": "freeze"},
    ]
    ruta = tmp_path / "dataset.json"

    guardar_dataset(ejemplos, ruta)

    assert cargar_dataset(ruta) == ejemplos


def prueba_el_dataset_cacheado_en_el_repo_tiene_las_486_filas() -> None:
    ejemplos = cargar_dataset()

    assert len(ejemplos) == 486
    assert all(e["transcripcion"] and e["intencion"] for e in ejemplos)


def prueba_la_muestra_cacheada_tiene_3_por_cada_una_de_las_14_intenciones() -> None:
    muestra = cargar_dataset(RUTA_MUESTRA_POR_DEFECTO)

    assert len(muestra) == 42
    conteos: dict[str, int] = {}
    for ejemplo in muestra:
        conteos[ejemplo["intencion"]] = conteos.get(ejemplo["intencion"], 0) + 1
    assert set(conteos) == {
        "abroad",
        "address",
        "app_error",
        "atm_limit",
        "balance",
        "business_loan",
        "card_issues",
        "cash_deposit",
        "direct_debit",
        "freeze",
        "high_value_payment",
        "joint_account",
        "latest_transactions",
        "pay_bill",
    }
    assert all(cantidad == 3 for cantidad in conteos.values())


def prueba_muestrear_estratificado_es_reproducible_con_la_misma_semilla() -> None:
    ejemplos: list[EjemploIntencion] = [
        EjemploIntencion(transcripcion=f"ejemplo {i}", intencion="freeze") for i in range(10)
    ]
    ejemplos += [
        EjemploIntencion(transcripcion=f"ejemplo balance {i}", intencion="balance")
        for i in range(10)
    ]

    primera = muestrear_estratificado(ejemplos, por_intencion=2, semilla=1)
    segunda = muestrear_estratificado(ejemplos, por_intencion=2, semilla=1)

    assert primera == segunda
    assert len(primera) == 4


def prueba_muestrear_estratificado_no_pide_mas_de_lo_que_hay() -> None:
    ejemplos: list[EjemploIntencion] = [{"transcripcion": "unico", "intencion": "freeze"}]

    muestra = muestrear_estratificado(ejemplos, por_intencion=3)

    assert muestra == ejemplos
