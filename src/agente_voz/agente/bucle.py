from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

from google import genai
from google.genai import types

from agente_voz.agente.sesion import Sesion
from agente_voz.herramientas import herramientas
from agente_voz.herramientas.autorizacion import AutorizacionError
from agente_voz.herramientas.cliente_banco import ClienteBanco

# "gemini-2.5-flash" quedo deprecado para cuentas nuevas (confirmado con un 404 real de
# la API el 2026-09-16, que recomendaba pasar a "gemini-3.6-flash"). Revisar en
# https://aistudio.google.com si aparecio uno mas nuevo antes de asumir que este sigue vigente.
MODELO_POR_DEFECTO = "gemini-3.6-flash"

NOMBRE_BANCO = "Banco Rio de la Plata"

INSTRUCCION_DEL_SISTEMA = f"""
Sos el asistente de voz de {NOMBRE_BANCO}, un banco uruguayo. Hablas en espanol
rioplatense, con "vos", de forma clara y cordial.

Podes ayudar con: consultar movimientos recientes, bloquear una tarjeta, abrir una
disputa por un cargo, y responder preguntas sobre politicas del banco. Cualquier otro
pedido, derivalo a un humano.

Reglas que segui siempre:
- Antes de consultar movimientos, bloquear una tarjeta o abrir una disputa, verifica la
  identidad del cliente (pedile la cedula y la fecha de nacimiento).
- Bloquear una tarjeta y abrir una disputa son acciones irreversibles: antes de
  ejecutarlas de verdad, repetile la accion al cliente en tus propias palabras y espera
  un "si" claro. Recien ahi volve a llamar a la herramienta con confirmado=true.
- Nunca digas ni repitas un numero de tarjeta completo; solo los ultimos 4 digitos.
- Si el sistema te dice que la sesion esta bloqueada, derivala a un humano.
- Si no tenes una fuente (politica, movimiento, etc.) que respalde una respuesta, decilo
  en vez de inventar.
""".strip()


def _declaraciones_de_herramientas() -> list[types.Tool]:
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="verificar_identidad",
                    description=(
                        "Verifica la identidad del cliente con cedula y fecha de nacimiento."
                    ),
                    parameters_json_schema={
                        "type": "object",
                        "properties": {
                            "cedula": {
                                "type": "string",
                                "description": "Cedula uruguaya, ej: 1.234.567-8",
                            },
                            "fecha_nacimiento": {
                                "type": "string",
                                "description": "Formato YYYY-MM-DD",
                            },
                        },
                        "required": ["cedula", "fecha_nacimiento"],
                    },
                ),
                types.FunctionDeclaration(
                    name="obtener_movimientos",
                    description="Movimientos recientes de las cuentas del cliente verificado.",
                    parameters_json_schema={
                        "type": "object",
                        "properties": {
                            "limite": {
                                "type": "integer",
                                "description": "Cantidad maxima de movimientos por cuenta",
                            },
                        },
                    },
                ),
                types.FunctionDeclaration(
                    name="bloquear_tarjeta",
                    description=(
                        "Bloquea una tarjeta del cliente verificado. Accion irreversible: "
                        "requiere confirmacion explicita del cliente."
                    ),
                    parameters_json_schema={
                        "type": "object",
                        "properties": {
                            "ultimos_4_digitos": {"type": "string"},
                            "confirmado": {
                                "type": "boolean",
                                "description": (
                                    "true solo despues de que el cliente confirmo con un si claro"
                                ),
                            },
                        },
                        "required": ["ultimos_4_digitos", "confirmado"],
                    },
                ),
                types.FunctionDeclaration(
                    name="abrir_disputa",
                    description=(
                        "Abre una disputa por un cargo del cliente verificado. Accion "
                        "irreversible: requiere confirmacion explicita del cliente."
                    ),
                    parameters_json_schema={
                        "type": "object",
                        "properties": {
                            "comercio": {"type": "string"},
                            "monto": {"type": "number"},
                            "motivo": {"type": "string"},
                            "confirmado": {
                                "type": "boolean",
                                "description": (
                                    "true solo despues de que el cliente confirmo con un si claro"
                                ),
                            },
                        },
                        "required": ["comercio", "monto", "motivo", "confirmado"],
                    },
                ),
                types.FunctionDeclaration(
                    name="buscar_politicas",
                    description="Busca en las politicas del banco (comisiones, plazos, limites).",
                    parameters_json_schema={
                        "type": "object",
                        "properties": {"pregunta": {"type": "string"}},
                        "required": ["pregunta"],
                    },
                ),
                types.FunctionDeclaration(
                    name="derivar_a_humano",
                    description="Deriva la conversacion a un asesor humano.",
                    parameters_json_schema={
                        "type": "object",
                        "properties": {"motivo": {"type": "string"}},
                        "required": ["motivo"],
                    },
                ),
            ]
        )
    ]


EjecutorDeHerramienta = Callable[..., Awaitable[str]]


@dataclass(frozen=True)
class _EntradaHerramienta:
    funcion: EjecutorDeHerramienta
    necesita_banco: bool


_REGISTRO: dict[str, _EntradaHerramienta] = {
    "verificar_identidad": _EntradaHerramienta(herramientas.verificar_identidad, True),
    "obtener_movimientos": _EntradaHerramienta(herramientas.obtener_movimientos, True),
    "bloquear_tarjeta": _EntradaHerramienta(herramientas.bloquear_tarjeta, True),
    "abrir_disputa": _EntradaHerramienta(herramientas.abrir_disputa, True),
    "buscar_politicas": _EntradaHerramienta(herramientas.buscar_politicas, False),
    "derivar_a_humano": _EntradaHerramienta(herramientas.derivar_a_humano, False),
}


class Agente:
    """Loop de herramientas escrito a mano contra el SDK de Gemini (sin framework de
    agentes). Una instancia = una sesion + una conversacion.
    """

    def __init__(
        self,
        sesion: Sesion,
        banco: ClienteBanco,
        *,
        modelo: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._sesion = sesion
        self._banco = banco
        clave = api_key or os.environ.get("GEMINI_API_KEY")
        if not clave:
            raise RuntimeError("Falta GEMINI_API_KEY (variable de entorno o parametro api_key).")
        cliente = genai.Client(api_key=clave)
        self._chat = cliente.aio.chats.create(
            model=modelo or os.environ.get("GEMINI_MODEL") or MODELO_POR_DEFECTO,
            config=types.GenerateContentConfig(
                system_instruction=INSTRUCCION_DEL_SISTEMA,
                # cast: el campo `tools` del SDK esta tipado como una union invariante
                # (list[Tool | Callable | ...]) que no acepta directamente un list[Tool].
                tools=cast(types.ToolListUnion, _declaraciones_de_herramientas()),
            ),
        )

    async def _ejecutar_herramienta(self, llamada: types.FunctionCall) -> dict[str, Any]:
        entrada = _REGISTRO.get(llamada.name) if llamada.name else None
        if entrada is None:
            return {"error": f"Herramienta desconocida: {llamada.name}"}

        argumentos = llamada.args or {}
        args_llamada = (self._sesion, self._banco) if entrada.necesita_banco else (self._sesion,)
        try:
            resultado = await entrada.funcion(*args_llamada, **argumentos)
        except AutorizacionError as error:
            resultado = str(error)
        return {"resultado": resultado}

    async def enviar(self, mensaje: str) -> str:
        respuesta = await self._chat.send_message(mensaje)

        while respuesta.function_calls:
            partes_de_respuesta = [
                types.Part.from_function_response(
                    name=llamada.name or "",
                    response=await self._ejecutar_herramienta(llamada),
                )
                for llamada in respuesta.function_calls
            ]
            respuesta = await self._chat.send_message(partes_de_respuesta)

        return respuesta.text or ""
