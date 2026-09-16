from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Concatenate

from agente_voz.agente.sesion import Sesion


class AutorizacionError(Exception):
    """Base de los errores que rechazan una llamada a una herramienta sensible."""


class SesionNoVerificadaError(AutorizacionError):
    """La sesion todavia no verifico la identidad del cliente."""


class SesionBloqueadaError(AutorizacionError):
    """La sesion se bloqueo tras demasiados intentos fallidos de verificacion."""


def requiere_verificacion[**P, R](
    funcion: Callable[Concatenate[Sesion, P], R],
) -> Callable[Concatenate[Sesion, P], R]:
    """Rechaza la llamada a una herramienta sensible si la sesion no esta verificada
    o esta bloqueada. La decision se toma siempre aca, nunca en el prompt del modelo.
    """

    @functools.wraps(funcion)
    def envoltorio(sesion: Sesion, /, *args: P.args, **kwargs: P.kwargs) -> R:
        if sesion.bloqueada:
            raise SesionBloqueadaError(
                f"La sesion {sesion.id_sesion} esta bloqueada por demasiados intentos "
                "fallidos de verificacion."
            )
        if not sesion.verificada:
            raise SesionNoVerificadaError(
                f"La sesion {sesion.id_sesion} no verifico la identidad del cliente todavia."
            )
        return funcion(sesion, *args, **kwargs)

    return envoltorio
