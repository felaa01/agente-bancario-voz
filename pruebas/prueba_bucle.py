import asyncio
from typing import cast

import pytest
from google.genai import types
from google.genai.chats import AsyncChat
from google.genai.errors import APIError

from agente_voz.agente.bucle import (
    _REGISTRO,
    _REINTENTOS_GEMINI,
    Agente,
    _declaraciones_de_herramientas,
    _enviar_con_reintentos,
)
from agente_voz.agente.sesion import Sesion
from agente_voz.herramientas.cliente_banco import ClienteBanco

NOMBRES_ESPERADOS = {
    "verificar_identidad",
    "consultar_saldo",
    "obtener_movimientos",
    "bloquear_tarjeta",
    "abrir_disputa",
    "buscar_politicas",
    "derivar_a_humano",
}


def prueba_las_declaraciones_cubren_las_siete_herramientas() -> None:
    (tool,) = _declaraciones_de_herramientas()
    declaraciones = tool.function_declarations
    assert declaraciones is not None

    nombres = {d.name for d in declaraciones}

    assert nombres == NOMBRES_ESPERADOS


def prueba_el_registro_cubre_las_siete_herramientas() -> None:
    assert set(_REGISTRO) == NOMBRES_ESPERADOS


def prueba_sin_api_key_falla_con_un_mensaje_claro(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    sesion = Sesion(id_sesion="s1")
    banco = ClienteBanco("http://127.0.0.1:9")

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        Agente(sesion, banco)


def _agente_de_prueba() -> Agente:
    sesion = Sesion(id_sesion="s1")
    banco = ClienteBanco("http://127.0.0.1:9")  # no se llega a usar en estas pruebas
    return Agente(sesion, banco, api_key="clave-de-prueba")


async def prueba_ejecutar_herramienta_desconocida() -> None:
    agente = _agente_de_prueba()

    resultado = await agente._ejecutar_herramienta(
        types.FunctionCall(name="herramienta_inventada", args={})
    )

    assert "error" in resultado


async def prueba_ejecutar_herramienta_sin_verificar_no_propaga_la_excepcion() -> None:
    agente = _agente_de_prueba()

    resultado = await agente._ejecutar_herramienta(
        types.FunctionCall(name="obtener_movimientos", args={})
    )

    assert "no verifico" in resultado["resultado"].lower()


async def prueba_ejecutar_buscar_politicas_no_necesita_banco() -> None:
    agente = _agente_de_prueba()

    resultado = await agente._ejecutar_herramienta(
        types.FunctionCall(name="buscar_politicas", args={"pregunta": "algo"})
    )

    assert "no tengo" in resultado["resultado"].lower()


async def prueba_herramienta_desconocida_no_queda_registrada() -> None:
    agente = _agente_de_prueba()

    await agente._ejecutar_herramienta(types.FunctionCall(name="herramienta_inventada", args={}))

    assert agente.herramientas_llamadas == []


async def prueba_herramienta_conocida_queda_registrada_aunque_falle_la_autorizacion() -> None:
    agente = _agente_de_prueba()

    await agente._ejecutar_herramienta(types.FunctionCall(name="obtener_movimientos", args={}))

    assert agente.herramientas_llamadas == ["obtener_movimientos"]


async def prueba_las_llamadas_se_acumulan_en_orden() -> None:
    agente = _agente_de_prueba()

    await agente._ejecutar_herramienta(
        types.FunctionCall(name="buscar_politicas", args={"pregunta": "algo"})
    )
    await agente._ejecutar_herramienta(types.FunctionCall(name="obtener_movimientos", args={}))

    assert agente.herramientas_llamadas == ["buscar_politicas", "obtener_movimientos"]


class _ChatFalso:
    """Doble de prueba para AsyncChat: no llama a la red, repite una secuencia de
    resultados fijada de antemano (éxito o APIError)."""

    def __init__(self, resultados: list[APIError | types.GenerateContentResponse]) -> None:
        self._resultados = resultados
        self.llamadas = 0

    async def send_message(
        self, mensaje: types.PartUnionDict | list[types.PartUnionDict]
    ) -> types.GenerateContentResponse:
        resultado = self._resultados[self.llamadas]
        self.llamadas += 1
        if isinstance(resultado, APIError):
            raise resultado
        return resultado


async def _sin_espera(segundos: float) -> None:
    return None


async def prueba_enviar_con_reintentos_reintenta_un_error_transitorio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(asyncio, "sleep", _sin_espera)
    chat = _ChatFalso([APIError(503, {}), types.GenerateContentResponse()])

    respuesta = await _enviar_con_reintentos(cast(AsyncChat, chat), "hola")

    assert chat.llamadas == 2
    assert respuesta.text is None


async def prueba_enviar_con_reintentos_no_reintenta_un_error_no_transitorio() -> None:
    chat = _ChatFalso([APIError(400, {})])

    with pytest.raises(APIError):
        await _enviar_con_reintentos(cast(AsyncChat, chat), "hola")

    assert chat.llamadas == 1


async def prueba_enviar_con_reintentos_relanza_tras_agotar_los_intentos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(asyncio, "sleep", _sin_espera)
    chat = _ChatFalso([APIError(503, {}) for _ in range(_REINTENTOS_GEMINI)])

    with pytest.raises(APIError):
        await _enviar_con_reintentos(cast(AsyncChat, chat), "hola")

    assert chat.llamadas == _REINTENTOS_GEMINI
