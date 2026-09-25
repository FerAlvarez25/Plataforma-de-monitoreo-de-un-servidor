import multiprocessing as mp

from servidor.componentes.procesamiento import cargador_cpu_main, trabajo_cpu
from servidor.shared.cola_pq import ColaProductorConsumidor
from servidor.shared.estado import crear_estado


def test_trabajo_cpu_determinista():
    assert trabajo_cpu(10, 7) == trabajo_cpu(10, 7)
    assert trabajo_cpu(10, 7) != trabajo_cpu(10, 8)


def test_cargador_procesa_lote():
    e = crear_estado()
    cola_t = ColaProductorConsumidor(16, e._manager)
    cola_r = mp.Queue()
    for i in range(5):
        cola_t.put(i)
    cola_t.put(None)                     # centinela de fin
    p = mp.Process(target=cargador_cpu_main, args=(cola_t, cola_r, 5, 0))
    p.start()
    p.join(timeout=10)
    assert not p.is_alive()
    resultados = []
    while not cola_r.empty():
        resultados.append(cola_r.get())
    assert sorted(r["id"] for r in resultados) == [0, 1, 2, 3, 4]