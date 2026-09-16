from __future__ import annotations

import os
from types import TracebackType
from uuid import UUID

import httpx2

from agente_voz.api_banco.modelos import Cliente, Cuenta, Disputa, Movimiento, Tarjeta


class ClienteBanco:
    """Cliente HTTP hacia la API del banco (`api_banco/app.py`). El agente nunca
    accede a la base de datos directamente: le habla a esta API, como lo haria
    un sistema externo real.
    """

    def __init__(self, url_base: str | None = None) -> None:
        base = url_base or os.environ.get("URL_API_BANCO", "http://127.0.0.1:8000")
        self._cliente = httpx2.AsyncClient(base_url=base)

    async def cerrar(self) -> None:
        await self._cliente.aclose()

    async def __aenter__(self) -> ClienteBanco:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.cerrar()

    async def obtener_cliente_por_cedula(self, cedula: str) -> Cliente | None:
        respuesta = await self._cliente.get(f"/clientes/{cedula}")
        if respuesta.status_code == 404:
            return None
        respuesta.raise_for_status()
        return Cliente.model_validate(respuesta.json())

    async def obtener_cuentas(self, cliente_id: UUID) -> list[Cuenta]:
        respuesta = await self._cliente.get(f"/clientes/{cliente_id}/cuentas")
        respuesta.raise_for_status()
        return [Cuenta.model_validate(fila) for fila in respuesta.json()]

    async def obtener_tarjetas(self, cliente_id: UUID) -> list[Tarjeta]:
        respuesta = await self._cliente.get(f"/clientes/{cliente_id}/tarjetas")
        respuesta.raise_for_status()
        return [Tarjeta.model_validate(fila) for fila in respuesta.json()]

    async def obtener_movimientos(self, cuenta_id: UUID, limite: int = 20) -> list[Movimiento]:
        respuesta = await self._cliente.get(
            f"/cuentas/{cuenta_id}/movimientos", params={"limite": limite}
        )
        respuesta.raise_for_status()
        return [Movimiento.model_validate(fila) for fila in respuesta.json()]

    async def bloquear_tarjeta(self, tarjeta_id: UUID) -> Tarjeta | None:
        respuesta = await self._cliente.post(f"/tarjetas/{tarjeta_id}/bloquear")
        if respuesta.status_code == 404:
            return None
        respuesta.raise_for_status()
        return Tarjeta.model_validate(respuesta.json())

    async def crear_disputa(self, movimiento_id: UUID, cliente_id: UUID, motivo: str) -> Disputa:
        respuesta = await self._cliente.post(
            "/disputas",
            json={
                "movimiento_id": str(movimiento_id),
                "cliente_id": str(cliente_id),
                "motivo": motivo,
            },
        )
        respuesta.raise_for_status()
        return Disputa.model_validate(respuesta.json())
