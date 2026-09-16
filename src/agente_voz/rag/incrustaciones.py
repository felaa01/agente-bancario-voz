from __future__ import annotations

import contextlib

from fastembed import TextEmbedding
from fastembed.common.model_description import ModelSource, PoolingType

# multilingual-e5-small no viene soportado nativamente en fastembed (solo la variante large,
# de 1024 dimensiones). Se registra a mano apuntando a la conversion ONNX cuantizada (int8) que
# mantiene la comunidad en https://huggingface.co/Xenova/multilingual-e5-small.
NOMBRE_MODELO = "Xenova/multilingual-e5-small"
DIMENSION = 384

# Los modelos e5 se entrenaron distinguiendo el rol del texto con estos prefijos: sin ellos,
# la calidad de la busqueda empeora notoriamente.
_PREFIJO_CONSULTA = "query: "
_PREFIJO_PASAJE = "passage: "


def _registrar_modelo() -> None:
    # ValueError: ya registrado (por ejemplo, si el modulo se importa mas de una vez).
    with contextlib.suppress(ValueError):
        TextEmbedding.add_custom_model(
            model=NOMBRE_MODELO,
            pooling=PoolingType.MEAN,
            normalization=True,
            sources=ModelSource(hf=NOMBRE_MODELO),
            dim=DIMENSION,
            model_file="onnx/model_quantized.onnx",
            description="e5-small multilingue, conversion ONNX cuantizada (Xenova).",
        )


_registrar_modelo()

_modelo: TextEmbedding | None = None


def _obtener_modelo() -> TextEmbedding:
    global _modelo
    if _modelo is None:
        _modelo = TextEmbedding(model_name=NOMBRE_MODELO)
    return _modelo


def incrustar_consulta(texto: str) -> list[float]:
    """Genera el embedding de una consulta de busqueda del usuario."""
    (vector,) = _obtener_modelo().embed([_PREFIJO_CONSULTA + texto])
    return vector.tolist()  # type: ignore[no-any-return]


def incrustar_pasajes(textos: list[str]) -> list[list[float]]:
    """Genera los embeddings de una lista de fragmentos de documentos."""
    vectores = _obtener_modelo().embed([_PREFIJO_PASAJE + texto for texto in textos])
    return [vector.tolist() for vector in vectores]
