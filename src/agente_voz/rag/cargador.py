from __future__ import annotations

import asyncio
import re
from pathlib import Path

from agente_voz.api_banco.conexion import crear_pool
from agente_voz.rag.incrustaciones import incrustar_pasajes
from agente_voz.rag.repositorio import reemplazar_fragmentos_de_documento

DIRECTORIO_POLITICAS_POR_DEFECTO = Path("datos/politicas")

_SEPARADOR_DE_PARRAFOS = re.compile(r"\n\s*\n")


def dividir_en_fragmentos(contenido: str) -> list[str]:
    """Divide un documento en fragmentos por parrafo (separados por una linea en blanco).

    Los documentos de politicas son cortos y de un solo tema, asi que no hace falta un
    chunking mas sofisticado por tamano de token.
    """
    return [
        parrafo.strip() for parrafo in _SEPARADOR_DE_PARRAFOS.split(contenido) if parrafo.strip()
    ]


async def cargar_directorio(directorio: Path = DIRECTORIO_POLITICAS_POR_DEFECTO) -> int:
    """Carga (o recarga) todos los .md de un directorio en la tabla politicas.

    Devuelve la cantidad de documentos cargados.
    """
    # README.md es el placeholder con instrucciones del directorio, no una politica.
    archivos = sorted(p for p in directorio.glob("*.md") if p.name != "README.md")
    if not archivos:
        raise FileNotFoundError(f"No se encontraron documentos .md en {directorio}")

    pool = await crear_pool()
    try:
        for archivo in archivos:
            fragmentos = dividir_en_fragmentos(archivo.read_text(encoding="utf-8"))
            if not fragmentos:
                continue
            embeddings = incrustar_pasajes(fragmentos)
            await reemplazar_fragmentos_de_documento(pool, archivo.name, fragmentos, embeddings)
    finally:
        await pool.close()
    return len(archivos)


def main() -> None:
    cantidad = asyncio.run(cargar_directorio())
    print(f"Cargados {cantidad} documentos de politicas.")


if __name__ == "__main__":
    main()
