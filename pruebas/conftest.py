from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest_asyncio

from agente_voz.api_banco.conexion import crear_pool

TABLAS = "disputas, movimientos, tarjetas, cuentas, clientes"


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    conexion_pool = await crear_pool()
    async with conexion_pool.acquire() as conexion:
        await conexion.execute(f"TRUNCATE {TABLAS} RESTART IDENTITY CASCADE")
    yield conexion_pool
    await conexion_pool.close()
