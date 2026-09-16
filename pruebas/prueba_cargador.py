from __future__ import annotations

from agente_voz.rag.cargador import dividir_en_fragmentos


def prueba_divide_por_parrafo() -> None:
    contenido = "Primer parrafo.\n\nSegundo parrafo.\n\nTercer parrafo."
    assert dividir_en_fragmentos(contenido) == [
        "Primer parrafo.",
        "Segundo parrafo.",
        "Tercer parrafo.",
    ]


def prueba_ignora_lineas_en_blanco_de_mas_y_espacios() -> None:
    contenido = "  Primer parrafo.  \n\n\n\n   Segundo parrafo.\n"
    assert dividir_en_fragmentos(contenido) == ["Primer parrafo.", "Segundo parrafo."]


def prueba_documento_vacio_no_produce_fragmentos() -> None:
    assert dividir_en_fragmentos("   \n\n  \n") == []
