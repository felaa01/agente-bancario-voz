from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from agente_voz.api_banco import conexion, repositorio
from agente_voz.api_banco.modelos import Cliente, Cuenta, Disputa, Movimiento, Tarjeta


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    await conexion.inicializar_pool()
    yield
    await conexion.cerrar_pool()


app = FastAPI(title="API del banco (simulada)", lifespan=ciclo_de_vida)

Pool = Annotated[asyncpg.Pool, Depends(conexion.obtener_pool)]


@app.get("/clientes/{cedula}")
async def leer_cliente(cedula: str, pool: Pool) -> Cliente:
    cliente = await repositorio.obtener_cliente_por_cedula(pool, cedula)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente


@app.get("/clientes/{cliente_id}/cuentas")
async def leer_cuentas_de_cliente(cliente_id: UUID, pool: Pool) -> list[Cuenta]:
    return await repositorio.obtener_cuentas_de_cliente(pool, cliente_id)


@app.get("/cuentas/{cuenta_id}/movimientos")
async def leer_movimientos(cuenta_id: UUID, pool: Pool, limite: int = 20) -> list[Movimiento]:
    return await repositorio.obtener_movimientos(pool, cuenta_id, limite)


@app.get("/movimientos/{movimiento_id}")
async def leer_movimiento(movimiento_id: UUID, pool: Pool) -> Movimiento:
    movimiento = await repositorio.obtener_movimiento(pool, movimiento_id)
    if movimiento is None:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return movimiento


@app.get("/tarjetas/{tarjeta_id}")
async def leer_tarjeta(tarjeta_id: UUID, pool: Pool) -> Tarjeta:
    tarjeta = await repositorio.obtener_tarjeta(pool, tarjeta_id)
    if tarjeta is None:
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
    return tarjeta


@app.post("/tarjetas/{tarjeta_id}/bloquear")
async def bloquear_tarjeta(tarjeta_id: UUID, pool: Pool) -> Tarjeta:
    tarjeta = await repositorio.bloquear_tarjeta(pool, tarjeta_id)
    if tarjeta is None:
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
    return tarjeta


class SolicitudDisputa(BaseModel):
    movimiento_id: UUID
    cliente_id: UUID
    motivo: str


@app.post("/disputas")
async def abrir_disputa(solicitud: SolicitudDisputa, pool: Pool) -> Disputa:
    return await repositorio.crear_disputa(
        pool, solicitud.movimiento_id, solicitud.cliente_id, solicitud.motivo
    )
