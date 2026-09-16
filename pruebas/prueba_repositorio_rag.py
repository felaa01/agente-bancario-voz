from __future__ import annotations

import asyncpg

from agente_voz.rag.incrustaciones import incrustar_consulta, incrustar_pasajes
from agente_voz.rag.repositorio import buscar_hibrido, reemplazar_fragmentos_de_documento

_DOCUMENTOS = {
    "bloqueo_de_tarjetas.md": [
        "Para bloquear tu tarjeta de credito o debito, llama al 0800-BANCO o usa la app.",
        "El bloqueo es inmediato y podes pedir una tarjeta nueva en cualquier sucursal.",
    ],
    "horarios_de_atencion.md": [
        "Las sucursales atienden de lunes a viernes de 9 a 17 horas.",
        "La banca telefonica funciona las 24 horas, todos los dias.",
    ],
}


async def _cargar_documentos_de_prueba(pool: asyncpg.Pool) -> None:
    for documento, fragmentos in _DOCUMENTOS.items():
        embeddings = incrustar_pasajes(fragmentos)
        await reemplazar_fragmentos_de_documento(pool, documento, fragmentos, embeddings)


async def prueba_buscar_hibrido_encuentra_el_documento_relevante(pool: asyncpg.Pool) -> None:
    await _cargar_documentos_de_prueba(pool)

    consulta_embedding = incrustar_consulta("como bloqueo mi tarjeta")
    resultados = await buscar_hibrido(pool, "bloquear tarjeta", consulta_embedding, limite=3)

    assert resultados
    assert resultados[0].documento == "bloqueo_de_tarjetas.md"


async def prueba_recargar_un_documento_reemplaza_sus_fragmentos(pool: asyncpg.Pool) -> None:
    await _cargar_documentos_de_prueba(pool)

    fragmentos_nuevos = ["Version actualizada: el bloqueo ahora tambien se pide por WhatsApp."]
    embeddings_nuevos = incrustar_pasajes(fragmentos_nuevos)
    await reemplazar_fragmentos_de_documento(
        pool, "bloqueo_de_tarjetas.md", fragmentos_nuevos, embeddings_nuevos
    )

    filas = await pool.fetch(
        "SELECT contenido FROM politicas WHERE documento = $1", "bloqueo_de_tarjetas.md"
    )
    assert [f["contenido"] for f in filas] == fragmentos_nuevos
