import pytest

from agente_voz.agente.sesion import Sesion
from agente_voz.herramientas.autorizacion import (
    SesionBloqueadaError,
    SesionNoVerificadaError,
    requiere_verificacion,
)


@requiere_verificacion
def herramienta_de_prueba(sesion: Sesion, monto: int) -> str:
    return f"{sesion.cliente_id}:{monto}"


def prueba_rechaza_sesion_no_verificada() -> None:
    sesion = Sesion(id_sesion="s1")

    with pytest.raises(SesionNoVerificadaError):
        herramienta_de_prueba(sesion, 100)


def prueba_rechaza_sesion_bloqueada_aunque_diga_verificada() -> None:
    sesion = Sesion(id_sesion="s1", verificada=True, bloqueada=True)

    with pytest.raises(SesionBloqueadaError):
        herramienta_de_prueba(sesion, 100)


def prueba_permite_la_llamada_con_sesion_verificada() -> None:
    sesion = Sesion(id_sesion="s1")
    sesion.marcar_verificada(cliente_id="cliente-1")

    resultado = herramienta_de_prueba(sesion, 100)

    assert resultado == "cliente-1:100"
