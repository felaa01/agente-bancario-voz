from __future__ import annotations

import os

import asyncpg


def _dsn() -> str:
    usuario = os.environ.get("POSTGRES_USER", "agente_voz")
    contrasena = os.environ.get("POSTGRES_PASSWORD", "agente_voz")
    base_de_datos = os.environ.get("POSTGRES_DB", "agente_voz")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    puerto = os.environ.get("POSTGRES_PORT", "5432")
    return f"postgresql://{usuario}:{contrasena}@{host}:{puerto}/{base_de_datos}"


async def crear_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn=_dsn())


_pool: asyncpg.Pool | None = None


async def inicializar_pool() -> None:
    global _pool
    _pool = await crear_pool()


async def cerrar_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def obtener_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError(
            "El pool de conexiones no fue inicializado (falta el lifespan de FastAPI)."
        )
    return _pool
