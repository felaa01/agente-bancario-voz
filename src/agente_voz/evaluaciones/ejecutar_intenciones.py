from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import TypedDict

from google.genai.errors import APIError

from agente_voz.agente.bucle import Agente, construir_historial_verificado
from agente_voz.agente.sesion import Sesion
from agente_voz.evaluaciones.dataset_intenciones import (
    RUTA_MUESTRA_POR_DEFECTO as RUTA_DATASET_POR_DEFECTO,
)
from agente_voz.evaluaciones.dataset_intenciones import EjemploIntencion, cargar_dataset
from agente_voz.evaluaciones.mapeo_intenciones import MAPEO_INTENCION_A_HERRAMIENTA, es_correcto
from agente_voz.herramientas.cliente_banco import ClienteBanco

RUTA_RESULTADOS_POR_DEFECTO = Path("evaluaciones/reportes/intenciones.jsonl")

# El free tier de Gemini tiene límites bajos de RPM: se espera entre llamadas para no
# saturarlo. El reintento con backoff ante un 429/5xx ya lo hace Agente.enviar por su
# cuenta (ver bucle.py); duplicarlo acá los anidaría (el de acá reintentaría un
# agente.enviar que ya reintentó puertas adentro).
_ESPERA_ENTRE_LLAMADAS_SEG = 4.0

# Cliente ficticio que no existe en la base: no importa, porque solo medimos que
# herramienta intenta llamar el agente, no el resultado. Un cliente_id inexistente
# simplemente hace que la herramienta devuelva listas vacias en vez de fallar.
_CLIENTE_ID_FICTICIO = "00000000-0000-0000-0000-000000000000"
_CEDULA_FICTICIA = "1.234.567-8"
_FECHA_NACIMIENTO_FICTICIA = "1990-01-01"
_NOMBRE_FICTICIO = "Cliente de prueba"


class ResultadoEjemplo(TypedDict):
    indice: int
    intencion: str
    transcripcion: str
    esperado: str
    obtenido: str | None
    correcto: bool


async def evaluar_ejemplo(
    indice: int, ejemplo: EjemploIntencion, url_banco: str
) -> ResultadoEjemplo:
    esperado = MAPEO_INTENCION_A_HERRAMIENTA[ejemplo["intencion"]]
    sesion = Sesion(id_sesion=f"eval-intencion-{indice}")
    sesion.marcar_verificada(_CLIENTE_ID_FICTICIO)

    historial = construir_historial_verificado(
        _CEDULA_FICTICIA, _FECHA_NACIMIENTO_FICTICIA, _NOMBRE_FICTICIO
    )
    async with ClienteBanco(url_banco) as banco:
        agente = Agente(sesion, banco, historial_inicial=historial)
        await agente.enviar(ejemplo["transcripcion"])

    obtenido = agente.herramientas_llamadas[0] if agente.herramientas_llamadas else None
    return ResultadoEjemplo(
        indice=indice,
        intencion=ejemplo["intencion"],
        transcripcion=ejemplo["transcripcion"],
        esperado=esperado,
        obtenido=obtenido,
        correcto=es_correcto(esperado, obtenido),
    )


def _indices_ya_evaluados(ruta: Path) -> set[int]:
    if not ruta.exists():
        return set()
    with ruta.open(encoding="utf-8") as archivo:
        return {json.loads(linea)["indice"] for linea in archivo if linea.strip()}


def resumir(ruta: Path = RUTA_RESULTADOS_POR_DEFECTO) -> dict[str, float]:
    """Exactitud global y por intencion sobre los resultados acumulados hasta ahora."""
    if not ruta.exists():
        return {}
    resultados = [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines()]

    por_intencion: dict[str, list[bool]] = {}
    for resultado in resultados:
        por_intencion.setdefault(resultado["intencion"], []).append(resultado["correcto"])

    resumen = {
        intencion: sum(aciertos) / len(aciertos) for intencion, aciertos in por_intencion.items()
    }
    resumen["_global"] = sum(r["correcto"] for r in resultados) / len(resultados)
    return resumen


async def ejecutar(
    max_nuevos: int,
    url_banco: str,
    ruta_dataset: Path = RUTA_DATASET_POR_DEFECTO,
    ruta_resultados: Path = RUTA_RESULTADOS_POR_DEFECTO,
) -> None:
    dataset = cargar_dataset(ruta_dataset)
    ya_evaluados = _indices_ya_evaluados(ruta_resultados)
    pendientes = [(i, ej) for i, ej in enumerate(dataset) if i not in ya_evaluados][:max_nuevos]

    if not pendientes:
        print(f"Nada nuevo para evaluar: {len(ya_evaluados)}/{len(dataset)} ya completados.")
        return

    procesados = 0
    ruta_resultados.parent.mkdir(parents=True, exist_ok=True)
    with ruta_resultados.open("a", encoding="utf-8") as archivo:
        for indice, ejemplo in pendientes:
            try:
                resultado = await evaluar_ejemplo(indice, ejemplo, url_banco)
            except APIError as error:
                if error.code == 429:
                    print(
                        f"\nCuota agotada en el ejemplo [{indice}]: {error}\n"
                        "Lo que se proceso hasta aca ya quedo guardado. Reintentar manana."
                    )
                    break
                raise
            archivo.write(json.dumps(resultado, ensure_ascii=False) + "\n")
            archivo.flush()
            procesados += 1
            marca = "OK" if resultado["correcto"] else "MISS"
            print(
                f"[{indice}] {resultado['intencion']:20s} "
                f"esperado={resultado['esperado']:18s} obtenido={resultado['obtenido']!s:18s} "
                f"{marca}"
            )
            await asyncio.sleep(_ESPERA_ENTRE_LLAMADAS_SEG)

    total_completados = len(ya_evaluados) + procesados
    print(f"\nProcesados {procesados} nuevos. Total: {total_completados}/{len(dataset)}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evalua eleccion de herramienta con MInDS-14 es-ES contra el agente real."
    )
    parser.add_argument(
        "--max-nuevos",
        type=int,
        default=50,
        help="Cuantos ejemplos nuevos procesar (el free tier de Gemini no da para todos de una).",
    )
    parser.add_argument("--url-banco", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    asyncio.run(ejecutar(args.max_nuevos, args.url_banco))
    print(resumir())


if __name__ == "__main__":
    main()
