import datetime
from uuid import UUID

import asyncpg
import pytest

from agente_voz.agente.sesion import Sesion
from agente_voz.herramientas import herramientas
from agente_voz.herramientas.autorizacion import SesionBloqueadaError, SesionNoVerificadaError
from agente_voz.herramientas.cliente_banco import ClienteBanco
from agente_voz.rag.incrustaciones import incrustar_pasajes
from agente_voz.rag.repositorio import reemplazar_fragmentos_de_documento

CEDULA = "1.234.567-8"
FECHA_NACIMIENTO = "1990-01-01"


async def _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool: asyncpg.Pool) -> None:
    cliente_id = await pool.fetchval(
        """
        INSERT INTO clientes (nombre_completo, cedula, fecha_nacimiento, email, telefono)
        VALUES ('Cliente de prueba', $1, $2, 'p@ejemplo.com', '099123456')
        RETURNING id
        """,
        CEDULA,
        datetime.date.fromisoformat(FECHA_NACIMIENTO),
    )
    cuenta_id = await pool.fetchval(
        """
        INSERT INTO cuentas (cliente_id, numero_cuenta, moneda, tipo, saldo)
        VALUES ($1, '001-234567', 'UYU', 'caja_ahorro', 1000)
        RETURNING id
        """,
        cliente_id,
    )
    await pool.execute(
        """
        INSERT INTO tarjetas (cuenta_id, ultimos_4_digitos, tipo, vencimiento)
        VALUES ($1, '4242', 'debito', '2030-01-01')
        """,
        cuenta_id,
    )
    await pool.execute(
        """
        INSERT INTO movimientos (cuenta_id, monto, moneda, descripcion, comercio, tipo)
        VALUES ($1, 500, 'UYU', 'Compra de prueba', 'Comercio SA', 'debito')
        """,
        cuenta_id,
    )


async def prueba_verificar_identidad_correcta(pool: asyncpg.Pool, url_base_api: str) -> None:
    await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)
    sesion = Sesion(id_sesion="s1")

    async with ClienteBanco(url_base_api) as banco:
        resultado = await herramientas.verificar_identidad(sesion, banco, CEDULA, FECHA_NACIMIENTO)

    assert sesion.verificada
    assert "verificada" in resultado.lower()


async def prueba_verificar_identidad_incorrecta_registra_intento(
    pool: asyncpg.Pool, url_base_api: str
) -> None:
    await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)
    sesion = Sesion(id_sesion="s1")

    async with ClienteBanco(url_base_api) as banco:
        await herramientas.verificar_identidad(sesion, banco, CEDULA, "2000-01-01")

    assert not sesion.verificada
    assert sesion.intentos_fallidos == 1


async def prueba_verificar_identidad_bloquea_tras_tres_intentos(
    pool: asyncpg.Pool, url_base_api: str
) -> None:
    await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)
    sesion = Sesion(id_sesion="s1")

    async with ClienteBanco(url_base_api) as banco:
        for _ in range(3):
            await herramientas.verificar_identidad(sesion, banco, CEDULA, "2000-01-01")
        resultado = await herramientas.verificar_identidad(sesion, banco, CEDULA, FECHA_NACIMIENTO)

    assert sesion.bloqueada
    assert "bloquead" in resultado.lower()


async def prueba_consultar_saldo_sin_verificar_rechaza(
    pool: asyncpg.Pool, url_base_api: str
) -> None:
    sesion = Sesion(id_sesion="s1")

    async with ClienteBanco(url_base_api) as banco:
        with pytest.raises(SesionNoVerificadaError):
            await herramientas.consultar_saldo(sesion, banco)


async def prueba_consultar_saldo_verificada(pool: asyncpg.Pool, url_base_api: str) -> None:
    await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)
    sesion = Sesion(id_sesion="s1")

    async with ClienteBanco(url_base_api) as banco:
        await herramientas.verificar_identidad(sesion, banco, CEDULA, FECHA_NACIMIENTO)
        resultado = await herramientas.consultar_saldo(sesion, banco)

    assert "1000" in resultado
    assert "UYU" in resultado


async def prueba_obtener_movimientos_sin_verificar_rechaza(
    pool: asyncpg.Pool, url_base_api: str
) -> None:
    sesion = Sesion(id_sesion="s1")

    async with ClienteBanco(url_base_api) as banco:
        with pytest.raises(SesionNoVerificadaError):
            await herramientas.obtener_movimientos(sesion, banco)


async def prueba_obtener_movimientos_verificada(pool: asyncpg.Pool, url_base_api: str) -> None:
    await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)
    sesion = Sesion(id_sesion="s1")

    async with ClienteBanco(url_base_api) as banco:
        await herramientas.verificar_identidad(sesion, banco, CEDULA, FECHA_NACIMIENTO)
        resultado = await herramientas.obtener_movimientos(sesion, banco)

    assert "Comercio SA" in resultado


async def prueba_obtener_movimientos_sin_movimientos_devuelve_mensaje(
    pool: asyncpg.Pool, url_base_api: str
) -> None:
    cliente_id = await pool.fetchval(
        """
        INSERT INTO clientes (nombre_completo, cedula, fecha_nacimiento, email, telefono)
        VALUES ('Sin movimientos', $1, $2, 'p@ejemplo.com', '099123456')
        RETURNING id
        """,
        CEDULA,
        datetime.date.fromisoformat(FECHA_NACIMIENTO),
    )
    await pool.execute(
        """
        INSERT INTO cuentas (cliente_id, numero_cuenta, moneda, tipo, saldo)
        VALUES ($1, '001-234567', 'UYU', 'caja_ahorro', 1000)
        """,
        cliente_id,
    )
    sesion = Sesion(id_sesion="s1")

    async with ClienteBanco(url_base_api) as banco:
        await herramientas.verificar_identidad(sesion, banco, CEDULA, FECHA_NACIMIENTO)
        resultado = await herramientas.obtener_movimientos(sesion, banco)

    assert "no hay movimientos" in resultado.lower()


async def prueba_bloquear_tarjeta_pide_confirmacion_antes_de_ejecutar(
    pool: asyncpg.Pool, url_base_api: str
) -> None:
    await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)
    sesion = Sesion(id_sesion="s1")

    async with ClienteBanco(url_base_api) as banco:
        await herramientas.verificar_identidad(sesion, banco, CEDULA, FECHA_NACIMIENTO)
        resultado = await herramientas.bloquear_tarjeta(sesion, banco, "4242", confirmado=False)
        assert sesion.cliente_id is not None
        tarjetas = await banco.obtener_tarjetas(UUID(sesion.cliente_id))

    assert "confirma" in resultado.lower()
    assert tarjetas[0].estado == "activa"


async def prueba_bloquear_tarjeta_confirmada_la_bloquea(
    pool: asyncpg.Pool, url_base_api: str
) -> None:
    await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)
    sesion = Sesion(id_sesion="s1")

    async with ClienteBanco(url_base_api) as banco:
        await herramientas.verificar_identidad(sesion, banco, CEDULA, FECHA_NACIMIENTO)
        resultado = await herramientas.bloquear_tarjeta(sesion, banco, "4242", confirmado=True)

    assert "bloquee" in resultado.lower()


async def prueba_bloquear_tarjeta_ya_bloqueada_es_idempotente(
    pool: asyncpg.Pool, url_base_api: str
) -> None:
    await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)
    sesion = Sesion(id_sesion="s1")

    async with ClienteBanco(url_base_api) as banco:
        await herramientas.verificar_identidad(sesion, banco, CEDULA, FECHA_NACIMIENTO)
        await herramientas.bloquear_tarjeta(sesion, banco, "4242", confirmado=True)
        resultado = await herramientas.bloquear_tarjeta(sesion, banco, "4242", confirmado=True)

    assert "ya estaba bloqueada" in resultado.lower()


async def prueba_bloquear_tarjeta_inexistente(pool: asyncpg.Pool, url_base_api: str) -> None:
    await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)
    sesion = Sesion(id_sesion="s1")

    async with ClienteBanco(url_base_api) as banco:
        await herramientas.verificar_identidad(sesion, banco, CEDULA, FECHA_NACIMIENTO)
        resultado = await herramientas.bloquear_tarjeta(sesion, banco, "9999", confirmado=True)

    assert "no encontre" in resultado.lower()


async def prueba_abrir_disputa_pide_confirmacion_antes_de_ejecutar(
    pool: asyncpg.Pool, url_base_api: str
) -> None:
    await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)
    sesion = Sesion(id_sesion="s1")

    async with ClienteBanco(url_base_api) as banco:
        await herramientas.verificar_identidad(sesion, banco, CEDULA, FECHA_NACIMIENTO)
        resultado = await herramientas.abrir_disputa(
            sesion, banco, "Comercio SA", 500.0, "No lo reconozco", confirmado=False
        )
        total = await pool.fetchval("SELECT count(*) FROM disputas")

    assert "confirma" in resultado.lower()
    assert total == 0


async def prueba_abrir_disputa_sin_movimiento_coincidente(
    pool: asyncpg.Pool, url_base_api: str
) -> None:
    await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)
    sesion = Sesion(id_sesion="s1")

    async with ClienteBanco(url_base_api) as banco:
        await herramientas.verificar_identidad(sesion, banco, CEDULA, FECHA_NACIMIENTO)
        resultado = await herramientas.abrir_disputa(
            sesion, banco, "Otro Comercio", 999.0, "No lo reconozco", confirmado=True
        )

    assert "no encontre" in resultado.lower()


async def prueba_abrir_disputa_confirmada_es_idempotente(
    pool: asyncpg.Pool, url_base_api: str
) -> None:
    await _crear_cliente_con_cuenta_tarjeta_y_movimiento(pool)
    sesion = Sesion(id_sesion="s1")

    async with ClienteBanco(url_base_api) as banco:
        await herramientas.verificar_identidad(sesion, banco, CEDULA, FECHA_NACIMIENTO)
        await herramientas.abrir_disputa(
            sesion, banco, "Comercio SA", 500.0, "No lo reconozco", confirmado=True
        )
        await herramientas.abrir_disputa(
            sesion, banco, "Comercio SA", 500.0, "No lo reconozco", confirmado=True
        )
        total = await pool.fetchval("SELECT count(*) FROM disputas")

    assert total == 1


async def prueba_bloqueada_rechaza_herramientas_sensibles(
    pool: asyncpg.Pool, url_base_api: str
) -> None:
    sesion = Sesion(id_sesion="s1", verificada=True, bloqueada=True)

    async with ClienteBanco(url_base_api) as banco:
        with pytest.raises(SesionBloqueadaError):
            await herramientas.obtener_movimientos(sesion, banco)


async def prueba_buscar_politicas_no_requiere_verificacion() -> None:
    sesion = Sesion(id_sesion="s1")

    resultado = await herramientas.buscar_politicas(sesion, None, "que tan rapido es una disputa")

    assert "no tengo" in resultado.lower()


async def prueba_buscar_politicas_sin_resultados_lo_dice_en_vez_de_inventar(
    pool: asyncpg.Pool,
) -> None:
    sesion = Sesion(id_sesion="s1")

    resultado = await herramientas.buscar_politicas(sesion, pool, "algo que no esta en ningun lado")

    assert "no encontre" in resultado.lower()


async def prueba_buscar_politicas_devuelve_el_fragmento_relevante(pool: asyncpg.Pool) -> None:
    embeddings = incrustar_pasajes(["Para bloquear tu tarjeta, llama al 0800-BANCO."])
    await reemplazar_fragmentos_de_documento(
        pool,
        "bloqueo_de_tarjetas.md",
        ["Para bloquear tu tarjeta, llama al 0800-BANCO."],
        embeddings,
    )
    sesion = Sesion(id_sesion="s1")

    resultado = await herramientas.buscar_politicas(sesion, pool, "como bloqueo mi tarjeta")

    assert "0800-banco" in resultado.lower()


async def prueba_derivar_a_humano_funciona_con_sesion_bloqueada() -> None:
    sesion = Sesion(id_sesion="s1", bloqueada=True)

    resultado = await herramientas.derivar_a_humano(sesion, "cliente enojado")

    assert "asesor humano" in resultado.lower()
