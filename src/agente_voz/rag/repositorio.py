from __future__ import annotations

import asyncpg

from agente_voz.rag.modelos import FragmentoPolitica

# El "60" de Reciprocal Rank Fusion es la constante k habitual en la literatura (Cormack et al.,
# 2009): amortigua la diferencia entre el primer puesto y el resto sin necesitar normalizar
# ts_rank y similitud coseno a una misma escala, que no son comparables entre si.
_K_RRF = 60


def _a_literal_vector(embedding: list[float]) -> str:
    return "[" + ",".join(str(valor) for valor in embedding) + "]"


async def reemplazar_fragmentos_de_documento(
    pool: asyncpg.Pool,
    documento: str,
    fragmentos: list[str],
    embeddings: list[list[float]],
) -> None:
    """Borra los fragmentos previos de un documento y carga los nuevos.

    Se usa al recargar datos/politicas/: permite reprocesar un documento completo sin
    dejar fragmentos viejos huerfanos si cambio la cantidad de fragmentos.
    """
    async with pool.acquire() as conexion, conexion.transaction():
        await conexion.execute("DELETE FROM politicas WHERE documento = $1", documento)
        for indice, (contenido, embedding) in enumerate(zip(fragmentos, embeddings, strict=True)):
            await conexion.execute(
                """
                INSERT INTO politicas (documento, fragmento_indice, contenido, embedding)
                VALUES ($1, $2, $3, $4::vector)
                """,
                documento,
                indice,
                contenido,
                _a_literal_vector(embedding),
            )


async def buscar_hibrido(
    pool: asyncpg.Pool,
    consulta_texto: str,
    consulta_embedding: list[float],
    limite: int = 5,
) -> list[FragmentoPolitica]:
    """Busca fragmentos de politicas combinando texto completo en espanol y similitud vectorial.

    Combina los dos rankings con Reciprocal Rank Fusion en vez de sumar los puntajes crudos.
    """
    filas = await pool.fetch(
        """
        WITH candidatos_texto AS (
            SELECT id, row_number() OVER (ORDER BY ts_rank(busqueda_texto, consulta) DESC) AS rango
            FROM politicas, plainto_tsquery('spanish', $1) AS consulta
            WHERE busqueda_texto @@ consulta
            LIMIT 20
        ),
        candidatos_vectoriales AS (
            SELECT id, row_number() OVER (ORDER BY embedding <=> $2::vector) AS rango
            FROM politicas
            ORDER BY embedding <=> $2::vector
            LIMIT 20
        )
        SELECT
            p.documento,
            p.fragmento_indice,
            p.contenido,
            COALESCE(1.0 / ($4 + ct.rango), 0) + COALESCE(1.0 / ($4 + cv.rango), 0) AS puntaje
        FROM politicas p
        LEFT JOIN candidatos_texto ct ON ct.id = p.id
        LEFT JOIN candidatos_vectoriales cv ON cv.id = p.id
        WHERE ct.id IS NOT NULL OR cv.id IS NOT NULL
        ORDER BY puntaje DESC
        LIMIT $3
        """,
        consulta_texto,
        _a_literal_vector(consulta_embedding),
        limite,
        _K_RRF,
    )
    return [
        FragmentoPolitica(
            documento=fila["documento"],
            fragmento_indice=fila["fragmento_indice"],
            contenido=fila["contenido"],
        )
        for fila in filas
    ]
