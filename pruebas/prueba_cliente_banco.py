from uuid import UUID

import asyncpg

from agente_voz.herramientas.cliente_banco import ClienteBanco


async def _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool: asyncpg.Pool) -> dict[str, UUID]:
    cliente_id = await pool.fetchval(
        """
        INSERT INTO clientes (nombre_completo, cedula, fecha_nacimiento, email, telefono)
        VALUES ('Cliente de prueba', '1.234.567-8', '1990-01-01', 'p@ejemplo.com', '099123456')
        RETURNING id
        """
    )
    cuenta_id = await pool.fetchval(
        """
        INSERT INTO cuentas (cliente_id, numero_cuenta, moneda, tipo, saldo)
        VALUES ($1, '001-234567', 'UYU', 'caja_ahorro', 1000)
        RETURNING id
        """,
        cliente_id,
    )
    tarjeta_id = await pool.fetchval(
        """
        INSERT INTO tarjetas (cuenta_id, ultimos_4_digitos, tipo, vencimiento)
        VALUES ($1, '4242', 'debito', '2030-01-01')
        RETURNING id
        """,
        cuenta_id,
    )
    movimiento_id = await pool.fetchval(
        """
        INSERT INTO movimientos (cuenta_id, monto, moneda, descripcion, comercio, tipo)
        VALUES ($1, 500, 'UYU', 'Compra de prueba', 'Comercio SA', 'debito')
        RETURNING id
        """,
        cuenta_id,
    )
    return {
        "cliente_id": cliente_id,
        "cuenta_id": cuenta_id,
        "tarjeta_id": tarjeta_id,
        "movimiento_id": movimiento_id,
    }


async def prueba_obtener_cliente_por_cedula(pool: asyncpg.Pool, url_base_api: str) -> None:
    await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)

    async with ClienteBanco(url_base_api) as banco:
        cliente = await banco.obtener_cliente_por_cedula("1.234.567-8")

    assert cliente is not None
    assert cliente.cedula == "1.234.567-8"


async def prueba_obtener_cliente_por_cedula_inexistente(
    pool: asyncpg.Pool, url_base_api: str
) -> None:
    async with ClienteBanco(url_base_api) as banco:
        cliente = await banco.obtener_cliente_por_cedula("0.000.000-0")

    assert cliente is None


async def prueba_obtener_cuentas_y_movimientos(pool: asyncpg.Pool, url_base_api: str) -> None:
    datos = await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)

    async with ClienteBanco(url_base_api) as banco:
        cuentas = await banco.obtener_cuentas(datos["cliente_id"])
        movimientos = await banco.obtener_movimientos(cuentas[0].id)

    assert len(cuentas) == 1
    assert len(movimientos) == 1
    assert movimientos[0].comercio == "Comercio SA"


async def prueba_obtener_tarjetas(pool: asyncpg.Pool, url_base_api: str) -> None:
    datos = await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)

    async with ClienteBanco(url_base_api) as banco:
        tarjetas = await banco.obtener_tarjetas(datos["cliente_id"])

    assert len(tarjetas) == 1
    assert tarjetas[0].ultimos_4_digitos == "4242"


async def prueba_bloquear_tarjeta(pool: asyncpg.Pool, url_base_api: str) -> None:
    datos = await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)

    async with ClienteBanco(url_base_api) as banco:
        tarjeta = await banco.bloquear_tarjeta(datos["tarjeta_id"])

    assert tarjeta is not None
    assert tarjeta.estado == "bloqueada"


async def prueba_bloquear_tarjeta_inexistente_devuelve_none(
    pool: asyncpg.Pool, url_base_api: str
) -> None:
    await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)

    async with ClienteBanco(url_base_api) as banco:
        tarjeta = await banco.bloquear_tarjeta(UUID("00000000-0000-0000-0000-000000000000"))

    assert tarjeta is None


async def prueba_crear_disputa(pool: asyncpg.Pool, url_base_api: str) -> None:
    datos = await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)

    async with ClienteBanco(url_base_api) as banco:
        disputa = await banco.crear_disputa(
            datos["movimiento_id"], datos["cliente_id"], motivo="No reconozco el cargo"
        )

    assert disputa.movimiento_id == datos["movimiento_id"]
    assert disputa.estado == "abierta"
