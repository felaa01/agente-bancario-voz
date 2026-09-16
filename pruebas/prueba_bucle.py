import pytest
from google.genai import types

from agente_voz.agente.bucle import _REGISTRO, Agente, _declaraciones_de_herramientas
from agente_voz.agente.sesion import Sesion
from agente_voz.herramientas.cliente_banco import ClienteBanco

NOMBRES_ESPERADOS = {
    "verificar_identidad",
    "obtener_movimientos",
    "bloquear_tarjeta",
    "abrir_disputa",
    "buscar_politicas",
    "derivar_a_humano",
}


def prueba_las_declaraciones_cubren_las_seis_herramientas() -> None:
    (tool,) = _declaraciones_de_herramientas()
    declaraciones = tool.function_declarations
    assert declaraciones is not None

    nombres = {d.name for d in declaraciones}

    assert nombres == NOMBRES_ESPERADOS


def prueba_el_registro_cubre_las_seis_herramientas() -> None:
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
