from __future__ import annotations

import math

from agente_voz.rag.incrustaciones import DIMENSION, incrustar_consulta, incrustar_pasajes


def prueba_la_dimension_del_embedding_es_la_esperada() -> None:
    vector = incrustar_consulta("como bloqueo mi tarjeta")
    assert len(vector) == DIMENSION


def prueba_los_embeddings_quedan_normalizados() -> None:
    vector = incrustar_consulta("como bloqueo mi tarjeta")
    norma = math.sqrt(sum(x * x for x in vector))
    assert math.isclose(norma, 1.0, abs_tol=1e-3)


def prueba_un_pasaje_relacionado_tiene_mayor_similitud_que_uno_que_no_lo_esta() -> None:
    consulta = incrustar_consulta("como bloqueo mi tarjeta de credito")
    pasaje_relacionado, pasaje_no_relacionado = incrustar_pasajes(
        [
            "Para bloquear tu tarjeta de credito o debito, llama al 0800 o usa la app.",
            "El horario de atencion de las sucursales es de 9 a 17.",
        ]
    )

    def similitud_coseno(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert similitud_coseno(consulta, pasaje_relacionado) > similitud_coseno(
        consulta, pasaje_no_relacionado
    )
