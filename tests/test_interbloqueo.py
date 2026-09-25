import threading

from servidor.componentes.administrativas import depurar_registro
from servidor.componentes.reportes import generar_resumen
from servidor.shared.estado import crear_estado


def test_orden_invertido_produce_espera_circular():
    e = crear_estado()
    hechos = {"r": False, "a": False}

    def r():
        generar_resumen(e)
        hechos["r"] = True

    def a():
        depurar_registro(e, limite=1, invertido=True)
        hechos["a"] = True

    t1 = threading.Thread(target=r, daemon=True)
    t2 = threading.Thread(target=a, daemon=True)
    t1.start()
    t2.start()
    t1.join(timeout=2)
    t2.join(timeout=2)
    assert t1.is_alive() and t2.is_alive()   # ambos esperan circularmente
    assert not hechos["r"] and not hechos["a"]


def test_orden_uniforme_termina():
    e = crear_estado()
    hechos = {"r": False, "a": False}

    def r():
        generar_resumen(e)
        hechos["r"] = True

    def a():
        depurar_registro(e, limite=1, invertido=False)
        hechos["a"] = True

    t1 = threading.Thread(target=r, daemon=True)
    t2 = threading.Thread(target=a, daemon=True)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert hechos["r"] and hechos["a"]