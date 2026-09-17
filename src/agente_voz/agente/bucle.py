from __future__ import annotations

import asyncio
import os
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

import asyncpg
from google import genai
from google.genai import types
from google.genai.chats import AsyncChat
from google.genai.errors import APIError

from agente_voz.agente.sesion import Sesion
from agente_voz.herramientas import herramientas
from agente_voz.herramientas.autorizacion import AutorizacionError
from agente_voz.herramientas.cliente_banco import ClienteBanco

# "gemini-2.5-flash" quedo deprecado para cuentas nuevas (confirmado con un 404 real de
# la API el 2026-09-16, que recomendaba pasar a "gemini-3.6-flash"). Revisar en
# https://aistudio.google.com si aparecio uno mas nuevo antes de asumir que este sigue vigente.
MODELO_POR_DEFECTO = "gemini-3.6-flash"

# El free tier de Gemini devuelve 429 (cuota agotada) o 5xx (sobrecarga transitoria en
# los servidores de Google) con cierta frecuencia. Sin este reintento, cualquiera de los
# dos tira abajo la conversación entera (ver bug real del 2026-09-17: dos 503 seguidos
# mataron `make chat` en `cli.py`, perdiendo sesión e historial). Publica (no privada)
# porque `evaluaciones/ejecutar_intenciones.py` la reusa: si un APIError con uno de estos
# codigos llega hasta ahi, es porque _enviar_con_reintentos ya lo reintento sin exito, asi
# que tiene el mismo criterio para cortar prolijo en vez de reintentar (o reventar) de nuevo.
_REINTENTOS_GEMINI = 5
CODIGOS_TRANSITORIOS_GEMINI = {429, 500, 502, 503, 504}


async def _enviar_con_reintentos(
    chat: AsyncChat, mensaje: types.PartUnionDict | list[types.PartUnionDict]
) -> types.GenerateContentResponse:
    for intento in range(_REINTENTOS_GEMINI):
        try:
            return await chat.send_message(mensaje)
        except APIError as error:
            ultimo_intento = intento == _REINTENTOS_GEMINI - 1
            if error.code not in CODIGOS_TRANSITORIOS_GEMINI or ultimo_intento:
                raise
            await asyncio.sleep(2**intento + random.random())
    raise AssertionError("inalcanzable: el último intento siempre retorna o relanza")


NOMBRE_BANCO = "Banco Rio de la Plata"

INSTRUCCION_DEL_SISTEMA = f"""
Sos el asistente de voz de {NOMBRE_BANCO}, un banco uruguayo. Hablas en espanol
rioplatense, con "vos", de forma clara y cordial.

Podes ayudar con: consultar el saldo, consultar movimientos recientes, bloquear una
tarjeta, abrir una disputa por un cargo, y responder preguntas sobre politicas del
banco. Cualquier otro pedido, derivalo a un humano.

Reglas que segui siempre:
- Antes de consultar el saldo, movimientos, bloquear una tarjeta o abrir una disputa,
  verifica la identidad del cliente (pedile la cedula y la fecha de nacimiento).
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
                    name="consultar_saldo",
                    description="Saldo de las cuentas del cliente verificado.",
                    parameters_json_schema={"type": "object", "properties": {}},
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
    necesita_banco: bool = False
    necesita_bd: bool = False


_REGISTRO: dict[str, _EntradaHerramienta] = {
    "verificar_identidad": _EntradaHerramienta(
        herramientas.verificar_identidad, necesita_banco=True
    ),
    "consultar_saldo": _EntradaHerramienta(herramientas.consultar_saldo, necesita_banco=True),
    "obtener_movimientos": _EntradaHerramienta(
        herramientas.obtener_movimientos, necesita_banco=True
    ),
    "bloquear_tarjeta": _EntradaHerramienta(herramientas.bloquear_tarjeta, necesita_banco=True),
    "abrir_disputa": _EntradaHerramienta(herramientas.abrir_disputa, necesita_banco=True),
    "buscar_politicas": _EntradaHerramienta(herramientas.buscar_politicas, necesita_bd=True),
    "derivar_a_humano": _EntradaHerramienta(herramientas.derivar_a_humano),
}


def construir_historial_verificado(
    cedula: str, fecha_nacimiento: str, nombre_cliente: str
) -> list[types.ContentOrDict]:
    """Historial sintetico de una verificacion de identidad ya resuelta con exito.

    Marcar `Sesion.verificada` a mano no alcanza para esto: el modelo no tiene forma de
    ver el estado interno de la sesion, solo la conversacion. Si la sesion esta
    verificada en el servidor pero el modelo nunca "vio" una verificacion exitosa, igual
    va a pedir cedula y fecha de nacimiento de nuevo (paso correctamente cauteloso, pero
    hace que este historial sintetico sea necesario para evaluar el resto de las
    herramientas sin gastar una llamada real en repetir la verificacion cada vez).
    """
    return [
        types.Content(role="user", parts=[types.Part(text="Hola")]),
        types.Content(
            role="model",
            parts=[
                types.Part.from_function_call(
                    name="verificar_identidad",
                    args={"cedula": cedula, "fecha_nacimiento": fecha_nacimiento},
                )
            ],
        ),
        types.Content(
            role="user",
            parts=[
                types.Part.from_function_response(
                    name="verificar_identidad",
                    response={
                        "resultado": f"Identidad verificada correctamente para {nombre_cliente}."
                    },
                )
            ],
        ),
        types.Content(
            role="model",
            parts=[types.Part(text="Listo, ya verifique tu identidad. ¿En que te ayudo?")],
        ),
    ]


class Agente:
    """Loop de herramientas escrito a mano contra el SDK de Gemini (sin framework de
    agentes). Una instancia = una sesion + una conversacion.
    """

    def __init__(
        self,
        sesion: Sesion,
        banco: ClienteBanco,
        *,
        pool: asyncpg.Pool | None = None,
        modelo: str | None = None,
        api_key: str | None = None,
        historial_inicial: list[types.ContentOrDict] | None = None,
    ) -> None:
        self._sesion = sesion
        self._banco = banco
        self._pool = pool
        # Util para evaluacion (nivel 1, MInDS-14): que herramientas intento llamar el
        # modelo, en orden, sin importar si despues tuvieron exito o las rechazo la
        # autorizacion. No se resetea entre turnos: acumula toda la conversacion.
        self.herramientas_llamadas: list[str] = []
        clave = api_key or os.environ.get("GEMINI_API_KEY")
        if not clave:
            raise RuntimeError("Falta GEMINI_API_KEY (variable de entorno o parametro api_key).")
        # Se guarda como atributo (no una variable local descartable): Client.__del__
        # cierra el cliente HTTP subyacente cuando se recolecta como basura, y sin esta
        # referencia eso pasaba a mitad de conversacion, rompiendo la segunda llamada en
        # adelante en cuanto el modelo completaba una llamada a herramienta de verdad.
        self._cliente = genai.Client(api_key=clave)
        self._chat = self._cliente.aio.chats.create(
            model=modelo or os.environ.get("GEMINI_MODEL") or MODELO_POR_DEFECTO,
            history=historial_inicial,
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

        self.herramientas_llamadas.append(llamada.name or "")
        argumentos = llamada.args or {}
        args_llamada: tuple[Any, ...] = (self._sesion,)
        if entrada.necesita_banco:
            args_llamada += (self._banco,)
        if entrada.necesita_bd:
            args_llamada += (self._pool,)
        try:
            resultado = await entrada.funcion(*args_llamada, **argumentos)
        except AutorizacionError as error:
            resultado = str(error)
        return {"resultado": resultado}

    async def enviar(self, mensaje: str) -> str:
        respuesta = await _enviar_con_reintentos(self._chat, mensaje)

        while respuesta.function_calls:
            # Anotado con el alias exacto de send_message: list[types.Part] no alcanza
            # porque list es invariante (ver mypy si se saca esta anotacion).
            partes_de_respuesta: list[types.PartUnionDict] = [
                types.Part.from_function_response(
                    name=llamada.name or "",
                    response=await self._ejecutar_herramienta(llamada),
                )
                for llamada in respuesta.function_calls
            ]
            respuesta = await _enviar_con_reintentos(self._chat, partes_de_respuesta)

        return respuesta.text or ""
