from __future__ import annotations

from uuid import UUID

import asyncpg

from agente_voz.api_banco.modelos import Cliente, Cuenta, Disputa, Movimiento, Tarjeta


async def obtener_cliente_por_cedula(pool: asyncpg.Pool, cedula: str) -> Cliente | None:
    fila = await pool.fetchrow("SELECT * FROM clientes WHERE cedula = $1", cedula)
    return Cliente(**dict(fila)) if fila is not None else None


async def obtener_cuentas_de_cliente(pool: asyncpg.Pool, cliente_id: UUID) -> list[Cuenta]:
    filas = await pool.fetch("SELECT * FROM cuentas WHERE cliente_id = $1", cliente_id)
    return [Cuenta(**dict(fila)) for fila in filas]


async def obtener_movimientos(
    pool: asyncpg.Pool, cuenta_id: UUID, limite: int = 20
) -> list[Movimiento]:
    filas = await pool.fetch(
        "SELECT * FROM movimientos WHERE cuenta_id = $1 ORDER BY fecha DESC LIMIT $2",
        cuenta_id,
        limite,
    )
    return [Movimiento(**dict(fila)) for fila in filas]


async def obtener_movimiento(pool: asyncpg.Pool, movimiento_id: UUID) -> Movimiento | None:
    fila = await pool.fetchrow("SELECT * FROM movimientos WHERE id = $1", movimiento_id)
    return Movimiento(**dict(fila)) if fila is not None else None


async def obtener_tarjeta(pool: asyncpg.Pool, tarjeta_id: UUID) -> Tarjeta | None:
    fila = await pool.fetchrow("SELECT * FROM tarjetas WHERE id = $1", tarjeta_id)
    return Tarjeta(**dict(fila)) if fila is not None else None


async def bloquear_tarjeta(pool: asyncpg.Pool, tarjeta_id: UUID) -> Tarjeta | None:
    """Idempotente: bloquear una tarjeta ya bloqueada vuelve a devolver el mismo estado."""
    fila = await pool.fetchrow(
        "UPDATE tarjetas SET estado = 'bloqueada' WHERE id = $1 RETURNING *",
        tarjeta_id,
    )
    return Tarjeta(**dict(fila)) if fila is not None else None


async def crear_disputa(
    pool: asyncpg.Pool, movimiento_id: UUID, cliente_id: UUID, motivo: str
) -> Disputa:
    """Idempotente: un reintento con el mismo movimiento devuelve la disputa ya existente
    en vez de crear una duplicada (aprovecha el UNIQUE de movimiento_id en el esquema).
    """
    fila = await pool.fetchrow(
        """
        INSERT INTO disputas (movimiento_id, cliente_id, motivo)
        VALUES ($1, $2, $3)
        ON CONFLICT (movimiento_id) DO UPDATE SET movimiento_id = EXCLUDED.movimiento_id
        RETURNING *
        """,
        movimiento_id,
        cliente_id,
        motivo,
    )
    if fila is None:
        raise RuntimeError("crear_disputa: el INSERT ... RETURNING no devolvio una fila")
    return Disputa(**dict(fila))
