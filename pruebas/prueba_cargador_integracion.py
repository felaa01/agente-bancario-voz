from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest

from agente_voz.rag.cargador import cargar_directorio


async def prueba_cargar_directorio_inserta_los_fragmentos_de_cada_archivo(
    pool: asyncpg.Pool, tmp_path: Path
) -> None:
    (tmp_path / "bloqueo_de_tarjetas.md").write_text(
        "Para bloquear tu tarjeta llama al 0800-BANCO.\n\nEs inmediato.", encoding="utf-8"
    )
    (tmp_path / "horarios_de_atencion.md").write_text(
        "Las sucursales atienden de 9 a 17.", encoding="utf-8"
    )

    cantidad = await cargar_directorio(tmp_path)

    assert cantidad == 2
    filas = await pool.fetch("SELECT documento, fragmento_indice FROM politicas ORDER BY documento")
    assert [dict(fila) for fila in filas] == [
        {"documento": "bloqueo_de_tarjetas.md", "fragmento_indice": 0},
        {"documento": "bloqueo_de_tarjetas.md", "fragmento_indice": 1},
        {"documento": "horarios_de_atencion.md", "fragmento_indice": 0},
    ]


async def prueba_cargar_directorio_vacio_falla_con_un_error_claro(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await cargar_directorio(tmp_path)


async def prueba_cargar_directorio_ignora_el_readme(pool: asyncpg.Pool, tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "Instrucciones del directorio, no es una politica.", encoding="utf-8"
    )
    (tmp_path / "horarios_de_atencion.md").write_text(
        "Las sucursales atienden de 9 a 17.", encoding="utf-8"
    )

    cantidad = await cargar_directorio(tmp_path)

    assert cantidad == 1
    documentos = await pool.fetch("SELECT DISTINCT documento FROM politicas")
    assert [fila["documento"] for fila in documentos] == ["horarios_de_atencion.md"]
