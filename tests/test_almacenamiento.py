import multiprocessing as mp

from servidor.componentes.almacenamiento import almacenamiento_main, manejar_resultado
from servidor.shared.estado import crear_estado
from servidor.shared.registro import conteo_registrado


def test_manejar_resultado_sync_true():
    e = crear_estado()
    manejar_resultado(e, {"id": 1, "tipo": "reporte"}, sync=True)
    assert conteo_registrado(e) == 1


def test_almacenamiento_procesa_lote():
    e = crear_estado()
    cola_r = mp.Queue()
    for i in range(10):
        cola_r.put({"id": i, "tipo": "procesado"})
    for _ in range(3):
        cola_r.put(None)               # centinela por hilo escritor
    p = mp.Process(target=almacenamiento_main, args=(e, cola_r, 3, True))
    p.start()
    p.join(timeout=15)
    assert not p.is_alive()
    assert conteo_registrado(e) == 10