from __future__ import annotations

import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Iterator

import asyncpg
import pytest
import pytest_asyncio

from agente_voz.api_banco.conexion import crear_pool

TABLAS = "disputas, movimientos, tarjetas, cuentas, clientes"
PUERTO_API_DE_PRUEBA = 8123


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    conexion_pool = await crear_pool()
    async with conexion_pool.acquire() as conexion:
        await conexion.execute(f"TRUNCATE {TABLAS} RESTART IDENTITY CASCADE")
    yield conexion_pool
    await conexion_pool.close()


@pytest.fixture(scope="session")
def url_base_api() -> Iterator[str]:
    """Levanta la API FastAPI real como subproceso para las pruebas del cliente HTTP
    del agente, en un puerto distinto al de `make api` para no pisarlo.
    """
    url = f"http://127.0.0.1:{PUERTO_API_DE_PRUEBA}"
    proceso = subprocess.Popen(
        [
            "uv",
            "run",
            "uvicorn",
            "agente_voz.api_banco.app:app",
            "--port",
            str(PUERTO_API_DE_PRUEBA),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"{url}/docs", timeout=0.5)
                break
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.2)
        else:
            raise RuntimeError("La API de prueba no arranco a tiempo")
        yield url
    finally:
        proceso.terminate()
        proceso.wait(timeout=5)
