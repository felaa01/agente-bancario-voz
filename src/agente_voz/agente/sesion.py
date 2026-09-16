from __future__ import annotations

from dataclasses import dataclass

INTENTOS_MAXIMOS = 3


@dataclass
class Sesion:
    """Estado de una sesion de conversacion. Es la unica fuente de verdad sobre si el
    cliente ya verifico su identidad; ninguna herramienta debe confiar en otra cosa.
    """

    id_sesion: str
    cliente_id: str | None = None
    verificada: bool = False
    intentos_fallidos: int = 0
    bloqueada: bool = False

    def marcar_verificada(self, cliente_id: str) -> None:
        self.verificada = True
        self.cliente_id = cliente_id
        self.intentos_fallidos = 0

    def registrar_intento_fallido(self) -> None:
        if self.bloqueada:
            return
        self.intentos_fallidos += 1
        if self.intentos_fallidos >= INTENTOS_MAXIMOS:
            self.bloqueada = True
