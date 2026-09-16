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
