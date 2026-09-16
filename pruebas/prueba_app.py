from typing import cast
from uuid import UUID

from anyio.from_thread import BlockingPortal
from starlette.testclient import TestClient

from agente_voz.api_banco import conexion
from agente_voz.api_banco.app import app

TABLAS = "disputas, movimientos, tarjetas, cuentas, clientes"


def _portal(client: TestClient) -> BlockingPortal:
    """El portal solo es None antes de entrar al `with TestClient(app) as client`.
    Se castea porque Starlette lo tipa con un alias de anyio ya deprecado que mypy
    no puede resolver, y termina viendo el atributo como `Any`.
    """
    assert client.portal is not None
    return cast(BlockingPortal, client.portal)


async def _preparar_datos() -> dict[str, UUID]:
    pool = conexion.obtener_pool()
    async with pool.acquire() as conexion_sql:
        await conexion_sql.execute(f"TRUNCATE {TABLAS} RESTART IDENTITY CASCADE")

        cliente_id = await conexion_sql.fetchval(
            """
            INSERT INTO clientes (nombre_completo, cedula, fecha_nacimiento, email, telefono)
            VALUES ('Cliente de prueba', '1.234.567-8', '1990-01-01', 'p@ejemplo.com', '099123456')
            RETURNING id
            """
        )
        cuenta_id = await conexion_sql.fetchval(
            """
            INSERT INTO cuentas (cliente_id, numero_cuenta, moneda, tipo, saldo)
            VALUES ($1, '001-234567', 'UYU', 'caja_ahorro', 1000)
            RETURNING id
            """,
            cliente_id,
        )
        tarjeta_id = await conexion_sql.fetchval(
            """
            INSERT INTO tarjetas (cuenta_id, ultimos_4_digitos, tipo, vencimiento)
            VALUES ($1, '4242', 'debito', '2030-01-01')
            RETURNING id
            """,
            cuenta_id,
        )
        movimiento_id = await conexion_sql.fetchval(
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


def prueba_leer_cliente_existente() -> None:
    with TestClient(app) as client:
        _portal(client).call(_preparar_datos)
        respuesta = client.get("/clientes/1.234.567-8")

    assert respuesta.status_code == 200
    assert respuesta.json()["cedula"] == "1.234.567-8"


def prueba_leer_cliente_inexistente_devuelve_404() -> None:
    with TestClient(app) as client:
        _portal(client).call(_preparar_datos)
        respuesta = client.get("/clientes/0.000.000-0")

    assert respuesta.status_code == 404


def prueba_leer_cuentas_de_cliente() -> None:
    with TestClient(app) as client:
        datos = _portal(client).call(_preparar_datos)
        respuesta = client.get(f"/clientes/{datos['cliente_id']}/cuentas")

    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 1


def prueba_leer_movimiento_existente() -> None:
    with TestClient(app) as client:
        datos = _portal(client).call(_preparar_datos)
        respuesta = client.get(f"/movimientos/{datos['movimiento_id']}")

    assert respuesta.status_code == 200


def prueba_leer_movimiento_inexistente_devuelve_404() -> None:
    with TestClient(app) as client:
        _portal(client).call(_preparar_datos)
        respuesta = client.get("/movimientos/00000000-0000-0000-0000-000000000000")

    assert respuesta.status_code == 404


def prueba_leer_tarjeta_existente() -> None:
    with TestClient(app) as client:
        datos = _portal(client).call(_preparar_datos)
        respuesta = client.get(f"/tarjetas/{datos['tarjeta_id']}")

    assert respuesta.status_code == 200


def prueba_leer_tarjeta_inexistente_devuelve_404() -> None:
    with TestClient(app) as client:
        _portal(client).call(_preparar_datos)
        respuesta = client.get("/tarjetas/00000000-0000-0000-0000-000000000000")

    assert respuesta.status_code == 404


def prueba_leer_movimientos_de_una_cuenta() -> None:
    with TestClient(app) as client:
        datos = _portal(client).call(_preparar_datos)
        respuesta = client.get(f"/cuentas/{datos['cuenta_id']}/movimientos")

    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 1


def prueba_bloquear_tarjeta() -> None:
    with TestClient(app) as client:
        datos = _portal(client).call(_preparar_datos)
        respuesta = client.post(f"/tarjetas/{datos['tarjeta_id']}/bloquear")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "bloqueada"


def prueba_bloquear_tarjeta_inexistente_devuelve_404() -> None:
    with TestClient(app) as client:
        _portal(client).call(_preparar_datos)
        respuesta = client.post("/tarjetas/00000000-0000-0000-0000-000000000000/bloquear")

    assert respuesta.status_code == 404


def prueba_abrir_disputa_es_idempotente() -> None:
    with TestClient(app) as client:
        datos = _portal(client).call(_preparar_datos)
        cuerpo = {
            "movimiento_id": str(datos["movimiento_id"]),
            "cliente_id": str(datos["cliente_id"]),
            "motivo": "No reconozco el cargo",
        }

        primera = client.post("/disputas", json=cuerpo)
        segunda = client.post("/disputas", json=cuerpo)

    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert primera.json()["id"] == segunda.json()["id"]
