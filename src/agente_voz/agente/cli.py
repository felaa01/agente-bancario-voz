from __future__ import annotations

import asyncio

from agente_voz.agente.bucle import Agente
from agente_voz.agente.sesion import Sesion
from agente_voz.api_banco.conexion import crear_pool
from agente_voz.herramientas.cliente_banco import ClienteBanco


async def _conversar() -> None:
    sesion = Sesion(id_sesion="cli")
    pool = await crear_pool()
    try:
        async with ClienteBanco() as banco:
            agente = Agente(sesion, banco, pool=pool)
            print("Chateando con el agente (Ctrl+D o 'salir' para terminar).")
            while True:
                try:
                    mensaje = input("vos> ")
                except EOFError:
                    break
                if mensaje.strip().lower() == "salir":
                    break
                respuesta = await agente.enviar(mensaje)
                print(f"agente> {respuesta}")
    finally:
        await pool.close()


def main() -> None:
    asyncio.run(_conversar())


if __name__ == "__main__":
    main()
