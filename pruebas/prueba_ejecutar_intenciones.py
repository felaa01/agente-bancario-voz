from __future__ import annotations

import json
from pathlib import Path

import pytest
from google.genai.errors import APIError

from agente_voz.agente.bucle import Agente
from agente_voz.evaluaciones import ejecutar_intenciones as modulo
from agente_voz.evaluaciones.dataset_intenciones import EjemploIntencion, guardar_dataset


def _enviar_falso(nombre_herramienta: str | None) -> object:
    async def _enviar(self: Agente, mensaje: str) -> str:
        if nombre_herramienta is not None:
            self.herramientas_llamadas.append(nombre_herramienta)
        return "respuesta simulada"

    return _enviar


async def prueba_evaluar_ejemplo_correcto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Agente, "enviar", _enviar_falso("bloquear_tarjeta"))
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    ejemplo: EjemploIntencion = {"transcripcion": "bloqueenme la tarjeta", "intencion": "freeze"}

    resultado = await modulo.evaluar_ejemplo(0, ejemplo, "http://127.0.0.1:9")

    assert resultado["esperado"] == "bloquear_tarjeta"
    assert resultado["obtenido"] == "bloquear_tarjeta"
    assert resultado["correcto"]


async def prueba_evaluar_ejemplo_incorrecto_sin_llamar_ninguna_herramienta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Agente, "enviar", _enviar_falso(None))
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    ejemplo: EjemploIntencion = {"transcripcion": "bloqueenme la tarjeta", "intencion": "freeze"}

    resultado = await modulo.evaluar_ejemplo(0, ejemplo, "http://127.0.0.1:9")

    assert resultado["obtenido"] is None
    assert not resultado["correcto"]


async def prueba_evaluar_ejemplo_fuera_de_alcance_acepta_derivar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Agente, "enviar", _enviar_falso("derivar_a_humano"))
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    ejemplo: EjemploIntencion = {
        "transcripcion": "quiero un prestamo",
        "intencion": "business_loan",
    }

    resultado = await modulo.evaluar_ejemplo(0, ejemplo, "http://127.0.0.1:9")

    assert resultado["esperado"] == "fuera_de_alcance"
    assert resultado["correcto"]


def prueba_indices_ya_evaluados_sobre_archivo_inexistente(tmp_path: Path) -> None:
    assert modulo._indices_ya_evaluados(tmp_path / "no_existe.jsonl") == set()


def prueba_resumir_calcula_exactitud_global_y_por_intencion(tmp_path: Path) -> None:
    ruta = tmp_path / "resultados.jsonl"
    filas = [
        {"indice": 0, "intencion": "freeze", "correcto": True},
        {"indice": 1, "intencion": "freeze", "correcto": False},
        {"indice": 2, "intencion": "balance", "correcto": True},
    ]
    ruta.write_text("\n".join(json.dumps(f) for f in filas), encoding="utf-8")

    resumen = modulo.resumir(ruta)

    assert resumen["freeze"] == 0.5
    assert resumen["balance"] == 1.0
    assert resumen["_global"] == pytest.approx(2 / 3)


async def prueba_ejecutar_es_reanudable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dataset: list[EjemploIntencion] = [
        {"transcripcion": "a", "intencion": "freeze"},
        {"transcripcion": "b", "intencion": "balance"},
        {"transcripcion": "c", "intencion": "pay_bill"},
    ]
    ruta_dataset = tmp_path / "dataset.json"
    guardar_dataset(dataset, ruta_dataset)
    ruta_resultados = tmp_path / "resultados.jsonl"

    indices_procesados: list[int] = []

    async def _evaluar_falso(
        indice: int, ejemplo: EjemploIntencion, url_banco: str
    ) -> modulo.ResultadoEjemplo:
        indices_procesados.append(indice)
        return {
            "indice": indice,
            "intencion": ejemplo["intencion"],
            "transcripcion": ejemplo["transcripcion"],
            "esperado": "fuera_de_alcance",
            "obtenido": None,
            "correcto": True,
        }

    monkeypatch.setattr(modulo, "evaluar_ejemplo", _evaluar_falso)
    monkeypatch.setattr(modulo, "_ESPERA_ENTRE_LLAMADAS_SEG", 0)

    await modulo.ejecutar(2, "http://x", ruta_dataset=ruta_dataset, ruta_resultados=ruta_resultados)
    assert indices_procesados == [0, 1]

    await modulo.ejecutar(2, "http://x", ruta_dataset=ruta_dataset, ruta_resultados=ruta_resultados)
    assert indices_procesados == [0, 1, 2]

    await modulo.ejecutar(2, "http://x", ruta_dataset=ruta_dataset, ruta_resultados=ruta_resultados)
    assert indices_procesados == [0, 1, 2]


async def prueba_ejecutar_para_en_seco_con_cuota_agotada_sin_perder_lo_ya_guardado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset: list[EjemploIntencion] = [
        {"transcripcion": "a", "intencion": "freeze"},
        {"transcripcion": "b", "intencion": "balance"},
    ]
    ruta_dataset = tmp_path / "dataset.json"
    guardar_dataset(dataset, ruta_dataset)
    ruta_resultados = tmp_path / "resultados.jsonl"

    async def _evaluar_falso(
        indice: int, ejemplo: EjemploIntencion, url_banco: str
    ) -> modulo.ResultadoEjemplo:
        if indice == 1:
            raise APIError(429, {"error": {"message": "cuota agotada"}})
        return {
            "indice": indice,
            "intencion": ejemplo["intencion"],
            "transcripcion": ejemplo["transcripcion"],
            "esperado": "fuera_de_alcance",
            "obtenido": None,
            "correcto": True,
        }

    monkeypatch.setattr(modulo, "evaluar_ejemplo", _evaluar_falso)
    monkeypatch.setattr(modulo, "_ESPERA_ENTRE_LLAMADAS_SEG", 0)

    await modulo.ejecutar(
        10, "http://x", ruta_dataset=ruta_dataset, ruta_resultados=ruta_resultados
    )

    assert modulo._indices_ya_evaluados(ruta_resultados) == {0}


async def prueba_ejecutar_para_en_seco_ante_sobrecarga_sostenida_de_gemini(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset: list[EjemploIntencion] = [
        {"transcripcion": "a", "intencion": "freeze"},
        {"transcripcion": "b", "intencion": "balance"},
    ]
    ruta_dataset = tmp_path / "dataset.json"
    guardar_dataset(dataset, ruta_dataset)
    ruta_resultados = tmp_path / "resultados.jsonl"

    async def _evaluar_falso(
        indice: int, ejemplo: EjemploIntencion, url_banco: str
    ) -> modulo.ResultadoEjemplo:
        if indice == 1:
            raise APIError(503, {"error": {"message": "high demand"}})
        return {
            "indice": indice,
            "intencion": ejemplo["intencion"],
            "transcripcion": ejemplo["transcripcion"],
            "esperado": "fuera_de_alcance",
            "obtenido": None,
            "correcto": True,
        }

    monkeypatch.setattr(modulo, "evaluar_ejemplo", _evaluar_falso)
    monkeypatch.setattr(modulo, "_ESPERA_ENTRE_LLAMADAS_SEG", 0)

    await modulo.ejecutar(
        10, "http://x", ruta_dataset=ruta_dataset, ruta_resultados=ruta_resultados
    )

    assert modulo._indices_ya_evaluados(ruta_resultados) == {0}


async def prueba_ejecutar_relanza_un_error_no_transitorio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset: list[EjemploIntencion] = [{"transcripcion": "a", "intencion": "freeze"}]
    ruta_dataset = tmp_path / "dataset.json"
    guardar_dataset(dataset, ruta_dataset)
    ruta_resultados = tmp_path / "resultados.jsonl"

    async def _evaluar_falso(
        indice: int, ejemplo: EjemploIntencion, url_banco: str
    ) -> modulo.ResultadoEjemplo:
        raise APIError(400, {"error": {"message": "pedido invalido"}})

    monkeypatch.setattr(modulo, "evaluar_ejemplo", _evaluar_falso)

    with pytest.raises(APIError):
        await modulo.ejecutar(
            10, "http://x", ruta_dataset=ruta_dataset, ruta_resultados=ruta_resultados
        )
