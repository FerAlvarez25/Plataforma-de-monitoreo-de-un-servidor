from concurrent.futures import ThreadPoolExecutor

from servidor.shared.estado import crear_estado
from servidor.shared.registro import conteo_registrado, listar_registros, registrar_tarea


def test_secuencial_sync_true():
    e = crear_estado()
    for i in range(100):
        registrar_tarea(e, i, "tipo_a", sync=True)
    assert conteo_registrado(e) == 100
    assert len(listar_registros(e)) == 100


def test_concurrencia_sync_true_consistente():
    e = crear_estado()
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda i: registrar_tarea(e, i, "a", sync=True), range(800)))
    assert conteo_registrado(e) == 800


def test_raza_sync_false_pierde_actualizaciones():
    perdidas = 0
    for _ in range(3):
        e = crear_estado()

        def reg(i):
            registrar_tarea(e, i, "a", sync=False)

        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(reg, range(800)))
        if conteo_registrado(e) < 800:
            perdidas += 1
    assert perdidas >= 1