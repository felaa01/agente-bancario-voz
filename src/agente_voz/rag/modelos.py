from __future__ import annotations

from pydantic import BaseModel


class FragmentoPolitica(BaseModel):
    documento: str
    fragmento_indice: int
    contenido: str
