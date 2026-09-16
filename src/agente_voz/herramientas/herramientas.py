from __future__ import annotations

from uuid import UUID

from agente_voz.agente.sesion import Sesion
from agente_voz.herramientas.autorizacion import requiere_verificacion
from agente_voz.herramientas.cliente_banco import ClienteBanco


def _id_cliente_verificado(sesion: Sesion) -> UUID:
    """`@requiere_verificacion` ya garantiza que la sesion este verificada, asi que
    `cliente_id` no puede ser None aca.
    """
    if sesion.cliente_id is None:
        raise RuntimeError("sesion verificada sin cliente_id: no deberia pasar nunca")
    return UUID(sesion.cliente_id)


async def verificar_identidad(
    sesion: Sesion, banco: ClienteBanco, cedula: str, fecha_nacimiento: str
) -> str:
    """No lleva @requiere_verificacion: es la herramienta que hace la verificacion.
    Por eso mismo, chequea 'bloqueada' a mano antes de intentar nada.
    """
    if sesion.bloqueada:
        return "La sesion esta bloqueada por demasiados intentos fallidos. Derivar a un humano."

    cliente = await banco.obtener_cliente_por_cedula(cedula)
    if cliente is None or cliente.fecha_nacimiento.isoformat() != fecha_nacimiento:
        sesion.registrar_intento_fallido()
        if sesion.bloqueada:
            return (
                "Identidad incorrecta. La sesion quedo bloqueada tras 3 intentos. "
                "Derivar a un humano."
            )
        return f"No se pudo verificar la identidad (intento {sesion.intentos_fallidos} de 3)."

    sesion.marcar_verificada(str(cliente.id))
    return f"Identidad verificada correctamente para {cliente.nombre_completo}."


@requiere_verificacion
async def obtener_movimientos(sesion: Sesion, banco: ClienteBanco, limite: int = 20) -> str:
    cliente_id = _id_cliente_verificado(sesion)
    cuentas = await banco.obtener_cuentas(cliente_id)

    lineas = [
        f"{movimiento.fecha:%Y-%m-%d} | {movimiento.tipo} | {movimiento.monto} "
        f"{movimiento.moneda} | {movimiento.comercio} | {movimiento.descripcion}"
        for cuenta in cuentas
        for movimiento in await banco.obtener_movimientos(cuenta.id, limite)
    ]
    if not lineas:
        return "No hay movimientos recientes."
    return "\n".join(lineas)


@requiere_verificacion
async def bloquear_tarjeta(
    sesion: Sesion, banco: ClienteBanco, ultimos_4_digitos: str, confirmado: bool
) -> str:
    cliente_id = _id_cliente_verificado(sesion)
    coincidencias = [
        tarjeta
        for tarjeta in await banco.obtener_tarjetas(cliente_id)
        if tarjeta.ultimos_4_digitos == ultimos_4_digitos
    ]

    if not coincidencias:
        return f"No encontre ninguna tarjeta terminada en {ultimos_4_digitos}."
    if len(coincidencias) > 1:
        return "Encontre mas de una tarjeta con esos digitos, no puedo continuar de forma segura."

    tarjeta = coincidencias[0]
    if tarjeta.estado == "bloqueada":
        return f"La tarjeta terminada en {ultimos_4_digitos} ya estaba bloqueada."
    if not confirmado:
        return (
            f"Vas a bloquear la tarjeta terminada en {ultimos_4_digitos}. Es una accion "
            "irreversible: confirma con el cliente con un si claro y recien ahi volve a "
            "llamar a esta herramienta con confirmado=true."
        )

    tarjeta_bloqueada = await banco.bloquear_tarjeta(tarjeta.id)
    if tarjeta_bloqueada is None:
        return f"No pude bloquear la tarjeta terminada en {ultimos_4_digitos}."
    return f"Listo, bloquee la tarjeta terminada en {ultimos_4_digitos}."


@requiere_verificacion
async def abrir_disputa(
    sesion: Sesion,
    banco: ClienteBanco,
    comercio: str,
    monto: float,
    motivo: str,
    confirmado: bool,
) -> str:
    cliente_id = _id_cliente_verificado(sesion)
    cuentas = await banco.obtener_cuentas(cliente_id)
    candidatos = [
        movimiento
        for cuenta in cuentas
        for movimiento in await banco.obtener_movimientos(cuenta.id)
        if movimiento.comercio.lower() == comercio.lower() and float(movimiento.monto) == monto
    ]

    if not candidatos:
        return f"No encontre ningun movimiento de {monto} en {comercio}."
    if len(candidatos) > 1:
        return "Encontre mas de un movimiento que coincide, necesito mas detalle para continuar."

    movimiento = candidatos[0]
    if not confirmado:
        return (
            f"Vas a abrir una disputa por {movimiento.monto} {movimiento.moneda} en {comercio} "
            f"con motivo '{motivo}'. Es una accion irreversible: confirma con el cliente con "
            "un si claro y recien ahi volve a llamar a esta herramienta con confirmado=true."
        )

    disputa = await banco.crear_disputa(movimiento.id, cliente_id, motivo)
    return f"Listo, abri la disputa por el cargo de {comercio} (id {disputa.id})."


async def buscar_politicas(sesion: Sesion, pregunta: str) -> str:
    """Sin @requiere_verificacion: preguntar por politicas no requiere ser cliente
    identificado. El RAG todavia no existe (es de la semana 2): responder que no
    hay base de politicas es la aplicacion honesta de la regla 'si ningun documento
    respalda la respuesta, decirlo en vez de adivinar'.
    """
    return (
        "Todavia no tengo la base de politicas del banco conectada, asi que no puedo "
        "responder eso con certeza. Te recomiendo derivarte con un humano si es urgente."
    )


async def derivar_a_humano(sesion: Sesion, motivo: str) -> str:
    """Sin @requiere_verificacion: pedir un humano tiene que funcionar siempre,
    incluso con la sesion bloqueada (es la salida esperada en ese caso)."""
    return f"Te derivo con un asesor humano. Motivo: {motivo}."
