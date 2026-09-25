import threading as th

from ..shared.registro import registrar_tarea


def manejar_resultado(estado, resultado, sync):
    registrar_tarea(estado, resultado["id"], resultado.get("tipo", "procesado"), sync=sync)


def almacenamiento_main(estado, cola_resultados, n_hilos, sync):
    def worker():
        for res in iter(cola_resultados.get, None):
            manejar_resultado(estado, res, sync)

    hilos = [th.Thread(target=worker) for _ in range(n_hilos)]
    for t in hilos:
        t.start()
    for t in hilos:
        t.join()