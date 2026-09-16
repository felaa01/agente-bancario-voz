"""Pruebas que llaman a la API real de Gemini. Quedan fuera del CI (@pytest.mark.en_vivo).

Para correrlas hace falta GEMINI_API_KEY en el entorno (por ejemplo, con
`uv run --env-file .env pytest -m en_vivo pruebas/prueba_bucle_en_vivo.py`).
"""

import datetime

import asyncpg
import pytest

from agente_voz.agente.bucle import Agente
from agente_voz.agente.sesion import Sesion
from agente_voz.herramientas.cliente_banco import ClienteBanco

CEDULA = "1.234.567-8"
FECHA_NACIMIENTO = "1990-01-01"


async def _crear_cliente(pool: asyncpg.Pool) -> None:
    await pool.execute(
        """
        INSERT INTO clientes (nombre_completo, cedula, fecha_nacimiento, email, telefono)
        VALUES ('Cliente de prueba', $1, $2, 'p@ejemplo.com', '099123456')
        """,
        CEDULA,
        datetime.date.fromisoformat(FECHA_NACIMIENTO),
    )


@pytest.mark.en_vivo
async def prueba_el_agente_saluda_y_explica_que_puede_hacer(url_base_api: str) -> None:
    sesion = Sesion(id_sesion="s1")
    async with ClienteBanco(url_base_api) as banco:
        agente = Agente(sesion, banco)
        respuesta = await agente.enviar("Hola")

    assert respuesta.strip() != ""


@pytest.mark.en_vivo
async def prueba_el_agente_pide_verificacion_antes_de_dar_movimientos(
    pool: asyncpg.Pool, url_base_api: str
) -> None:
    await _crear_cliente(pool)
    sesion = Sesion(id_sesion="s1")
    async with ClienteBanco(url_base_api) as banco:
        agente = Agente(sesion, banco)
        respuesta = await agente.enviar("Quiero ver mis ultimos movimientos")

    assert not sesion.verificada
    assert "cedula" in respuesta.lower() or "identidad" in respuesta.lower()
