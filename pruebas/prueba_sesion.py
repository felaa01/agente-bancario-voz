from agente_voz.agente.sesion import Sesion


def prueba_sesion_nueva_no_esta_verificada() -> None:
    sesion = Sesion(id_sesion="s1")

    assert not sesion.verificada
    assert not sesion.bloqueada
    assert sesion.cliente_id is None


def prueba_marcar_verificada_actualiza_el_estado() -> None:
    sesion = Sesion(id_sesion="s1")

    sesion.marcar_verificada(cliente_id="cliente-1")

    assert sesion.verificada
    assert sesion.cliente_id == "cliente-1"
    assert sesion.intentos_fallidos == 0


def prueba_dos_intentos_fallidos_no_bloquean_la_sesion() -> None:
    sesion = Sesion(id_sesion="s1")

    sesion.registrar_intento_fallido()
    sesion.registrar_intento_fallido()

    assert sesion.intentos_fallidos == 2
    assert not sesion.bloqueada


def prueba_tres_intentos_fallidos_bloquean_la_sesion() -> None:
    sesion = Sesion(id_sesion="s1")

    for _ in range(3):
        sesion.registrar_intento_fallido()

    assert sesion.bloqueada


def prueba_una_sesion_bloqueada_no_acumula_mas_intentos() -> None:
    sesion = Sesion(id_sesion="s1")

    for _ in range(5):
        sesion.registrar_intento_fallido()

    assert sesion.bloqueada
    assert sesion.intentos_fallidos == 3
