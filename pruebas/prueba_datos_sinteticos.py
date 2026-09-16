import asyncpg

from agente_voz.api_banco import datos_sinteticos


async def prueba_sembrar_crea_clientes_cuentas_y_movimientos(pool: asyncpg.Pool) -> None:
    await datos_sinteticos.sembrar()

    total_clientes = await pool.fetchval("SELECT count(*) FROM clientes")
    total_cuentas = await pool.fetchval("SELECT count(*) FROM cuentas")
    total_movimientos = await pool.fetchval("SELECT count(*) FROM movimientos")

    assert total_clientes == datos_sinteticos.CANTIDAD_CLIENTES
    assert total_cuentas >= total_clientes
    assert total_movimientos > 0
