from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TypedDict

# Solo texto: el audio de MInDS-14 (telefonico, 8 kHz) es para la evaluacion de voz de la
# semana 3. Se usa la API de datasets-server de HuggingFace en vez de la libreria `datasets`
# para no traer pyarrow y el resto de su stack solo para leer transcripcion + etiqueta.
_DATASET = "PolyAI/minds14"
_CONFIG = "es-ES"
_TAMANO_PAGINA = 100
_REINTENTOS = 3

# Orden de ClassLabel tal como lo define el dataset (confirmado contra el endpoint /info).
NOMBRES_INTENCIONES = [
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
]

RUTA_POR_DEFECTO = Path("evaluaciones/intenciones/minds14_es.json")
RUTA_MUESTRA_POR_DEFECTO = Path("evaluaciones/intenciones/muestra_es.json")

# El free tier de Gemini da 20 llamadas por dia (no por minuto) para gemini-3.6-flash:
# evaluar las 486 filas completas tomaria semanas. Para un proyecto de portfolio alcanza
# con una muestra chica que cubra las 14 categorias, no el dataset entero.
EJEMPLOS_POR_INTENCION_EN_MUESTRA = 3
_SEMILLA_MUESTRA = 42


class EjemploIntencion(TypedDict):
    transcripcion: str
    intencion: str


def _url_pagina(offset: int) -> str:
    dataset_codificado = _DATASET.replace("/", "%2F")
    return (
        "https://datasets-server.huggingface.co/rows"
        f"?dataset={dataset_codificado}&config={_CONFIG}&split=train"
        f"&offset={offset}&length={_TAMANO_PAGINA}"
    )


def _pedir_pagina(offset: int) -> dict[str, object]:
    ultimo_error: Exception | None = None
    for intento in range(_REINTENTOS):
        try:
            with urllib.request.urlopen(_url_pagina(offset), timeout=30) as respuesta:
                resultado: dict[str, object] = json.load(respuesta)
                return resultado
        except (urllib.error.URLError, TimeoutError) as error:
            ultimo_error = error
            time.sleep(2**intento)
    raise RuntimeError(f"No se pudo bajar la pagina offset={offset}") from ultimo_error


def descargar_dataset() -> list[EjemploIntencion]:
    """Descarga todas las (transcripcion, intencion) del split train de MInDS-14 es-ES."""
    ejemplos: list[EjemploIntencion] = []
    offset = 0
    while True:
        datos = _pedir_pagina(offset)
        filas = datos["rows"]
        assert isinstance(filas, list)
        if not filas:
            break
        for fila in filas:
            fila_datos = fila["row"]
            ejemplos.append(
                EjemploIntencion(
                    transcripcion=fila_datos["transcription"],
                    intencion=NOMBRES_INTENCIONES[fila_datos["intent_class"]],
                )
            )
        offset += _TAMANO_PAGINA
    return ejemplos


def guardar_dataset(ejemplos: list[EjemploIntencion], ruta: Path = RUTA_POR_DEFECTO) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(ejemplos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cargar_dataset(ruta: Path = RUTA_POR_DEFECTO) -> list[EjemploIntencion]:
    datos: list[EjemploIntencion] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


def muestrear_estratificado(
    ejemplos: list[EjemploIntencion],
    por_intencion: int = EJEMPLOS_POR_INTENCION_EN_MUESTRA,
    semilla: int = _SEMILLA_MUESTRA,
) -> list[EjemploIntencion]:
    """Elige `por_intencion` ejemplos al azar (con semilla fija, reproducible) de cada
    intencion presente, en vez de un muestreo uniforme que podria dejar afuera alguna
    de las 14 categorias por el desbalance del dataset.
    """
    aleatorio = random.Random(semilla)
    por_clase: dict[str, list[EjemploIntencion]] = {}
    for ejemplo in ejemplos:
        por_clase.setdefault(ejemplo["intencion"], []).append(ejemplo)

    muestra: list[EjemploIntencion] = []
    for intencion in sorted(por_clase):
        candidatos = por_clase[intencion]
        cantidad = min(por_intencion, len(candidatos))
        muestra.extend(aleatorio.sample(candidatos, cantidad))
    return muestra


def main() -> None:
    ejemplos = descargar_dataset()
    guardar_dataset(ejemplos)
    print(f"Descargados y cacheados {len(ejemplos)} ejemplos en {RUTA_POR_DEFECTO}.")

    muestra = muestrear_estratificado(ejemplos)
    guardar_dataset(muestra, RUTA_MUESTRA_POR_DEFECTO)
    print(f"Muestra estratificada de {len(muestra)} ejemplos en {RUTA_MUESTRA_POR_DEFECTO}.")


if __name__ == "__main__":
    main()
