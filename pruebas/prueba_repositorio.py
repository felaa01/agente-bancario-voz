from uuid import UUID

import asyncpg

from agente_voz.api_banco import repositorio


async def _crear_cliente(pool: asyncpg.Pool, cedula: str = "1.234.567-8") -> UUID:
    fila = await pool.fetchrow(
        """
        INSERT INTO clientes (nombre_completo, cedula, fecha_nacimiento, email, telefono)
        VALUES ('Cliente de prueba', $1, '1990-01-01', 'prueba@ejemplo.com', '099123456')
        RETURNING id
        """,
        cedula,
    )
    assert fila is not None
    return UUID(str(fila["id"]))


async def _crear_cuenta(pool: asyncpg.Pool, cliente_id: UUID) -> UUID:
    fila = await pool.fetchrow(
        """
        INSERT INTO cuentas (cliente_id, numero_cuenta, moneda, tipo, saldo)
        VALUES ($1, '001-234567', 'UYU', 'caja_ahorro', 1000)
        RETURNING id
        """,
        cliente_id,
    )
    assert fila is not None
    return UUID(str(fila["id"]))


async def _crear_tarjeta(pool: asyncpg.Pool, cuenta_id: UUID) -> UUID:
    fila = await pool.fetchrow(
        """
        INSERT INTO tarjetas (cuenta_id, ultimos_4_digitos, tipo, vencimiento)
        VALUES ($1, '4242', 'debito', '2030-01-01')
        RETURNING id
        """,
        cuenta_id,
    )
    assert fila is not None
    return UUID(str(fila["id"]))


async def _crear_movimiento(pool: asyncpg.Pool, cuenta_id: UUID) -> UUID:
    fila = await pool.fetchrow(
        """
        INSERT INTO movimientos (cuenta_id, monto, moneda, descripcion, comercio, tipo)
        VALUES ($1, 500, 'UYU', 'Compra de prueba', 'Comercio SA', 'debito')
        RETURNING id
        """,
        cuenta_id,
    )
    assert fila is not None
    return UUID(str(fila["id"]))


async def prueba_obtener_cliente_por_cedula_existente(pool: asyncpg.Pool) -> None:
    await _crear_cliente(pool, cedula="1.111.111-1")

    cliente = await repositorio.obtener_cliente_por_cedula(pool, "1.111.111-1")

    assert cliente is not None
    assert cliente.cedula == "1.111.111-1"


async def prueba_obtener_cliente_por_cedula_inexistente_devuelve_none(
    pool: asyncpg.Pool,
) -> None:
    cliente = await repositorio.obtener_cliente_por_cedula(pool, "9.999.999-9")

    assert cliente is None


async def prueba_obtener_cuentas_de_cliente(pool: asyncpg.Pool) -> None:
    cliente_id = await _crear_cliente(pool)
    await _crear_cuenta(pool, cliente_id)

    cuentas = await repositorio.obtener_cuentas_de_cliente(pool, cliente_id)

    assert len(cuentas) == 1
    assert cuentas[0].cliente_id == cliente_id


async def prueba_obtener_movimientos_de_una_cuenta(pool: asyncpg.Pool) -> None:
    cliente_id = await _crear_cliente(pool)
    cuenta_id = await _crear_cuenta(pool, cliente_id)
    await _crear_movimiento(pool, cuenta_id)

    movimientos = await repositorio.obtener_movimientos(pool, cuenta_id)

    assert len(movimientos) == 1
    assert movimientos[0].cuenta_id == cuenta_id


async def prueba_obtener_movimiento_inexistente_devuelve_none(pool: asyncpg.Pool) -> None:
    movimiento = await repositorio.obtener_movimiento(
        pool, UUID("00000000-0000-0000-0000-000000000000")
    )

    assert movimiento is None


async def prueba_obtener_tarjeta_inexistente_devuelve_none(pool: asyncpg.Pool) -> None:
    tarjeta = await repositorio.obtener_tarjeta(pool, UUID("00000000-0000-0000-0000-000000000000"))

    assert tarjeta is None


async def prueba_bloquear_tarjeta_activa(pool: asyncpg.Pool) -> None:
    cliente_id = await _crear_cliente(pool)
    cuenta_id = await _crear_cuenta(pool, cliente_id)
    tarjeta_id = await _crear_tarjeta(pool, cuenta_id)

    tarjeta = await repositorio.bloquear_tarjeta(pool, tarjeta_id)

    assert tarjeta is not None
    assert tarjeta.estado == "bloqueada"


async def prueba_bloquear_tarjeta_ya_bloqueada_es_idempotente(pool: asyncpg.Pool) -> None:
    cliente_id = await _crear_cliente(pool)
    cuenta_id = await _crear_cuenta(pool, cliente_id)
    tarjeta_id = await _crear_tarjeta(pool, cuenta_id)

    await repositorio.bloquear_tarjeta(pool, tarjeta_id)
    segundo_intento = await repositorio.bloquear_tarjeta(pool, tarjeta_id)

    assert segundo_intento is not None
    assert segundo_intento.estado == "bloqueada"


async def prueba_crear_disputa(pool: asyncpg.Pool) -> None:
    cliente_id = await _crear_cliente(pool)
    cuenta_id = await _crear_cuenta(pool, cliente_id)
    movimiento_id = await _crear_movimiento(pool, cuenta_id)

    disputa = await repositorio.crear_disputa(
        pool, movimiento_id, cliente_id, motivo="No reconozco el cargo"
    )

    assert disputa.movimiento_id == movimiento_id
    assert disputa.estado == "abierta"


async def prueba_crear_disputa_repetida_no_duplica(pool: asyncpg.Pool) -> None:
    cliente_id = await _crear_cliente(pool)
    cuenta_id = await _crear_cuenta(pool, cliente_id)
    movimiento_id = await _crear_movimiento(pool, cuenta_id)

    primera = await repositorio.crear_disputa(pool, movimiento_id, cliente_id, motivo="Motivo 1")
    segunda = await repositorio.crear_disputa(pool, movimiento_id, cliente_id, motivo="Motivo 2")

    assert primera.id == segunda.id
    total = await pool.fetchval(
        "SELECT count(*) FROM disputas WHERE movimiento_id = $1", movimiento_id
    )
    assert total == 1
