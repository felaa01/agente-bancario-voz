from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Moneda = Literal["UYU", "USD"]


class Cliente(BaseModel):
    id: UUID
    nombre_completo: str
    cedula: str
    fecha_nacimiento: datetime.date
    email: str
    telefono: str
    creado_en: datetime.datetime


class Cuenta(BaseModel):
    id: UUID
    cliente_id: UUID
    numero_cuenta: str
    moneda: Moneda
    tipo: Literal["caja_ahorro", "cuenta_corriente"]
    saldo: Decimal
    creado_en: datetime.datetime


class Tarjeta(BaseModel):
    id: UUID
    cuenta_id: UUID
    ultimos_4_digitos: str
    tipo: Literal["debito", "credito"]
    estado: Literal["activa", "bloqueada"]
    vencimiento: datetime.date
    creado_en: datetime.datetime


class Movimiento(BaseModel):
    id: UUID
    cuenta_id: UUID
    fecha: datetime.datetime
    monto: Decimal
    moneda: Moneda
    descripcion: str
    comercio: str
    tipo: Literal["debito", "credito"]


class Disputa(BaseModel):
    id: UUID
    movimiento_id: UUID
    cliente_id: UUID
    motivo: str
    estado: Literal["abierta", "en_revision", "resuelta", "rechazada"]
    creado_en: datetime.datetime
    resuelto_en: datetime.datetime | None
