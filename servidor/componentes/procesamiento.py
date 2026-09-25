import hashlib
import multiprocessing as mp
import threading as th

from ..shared.eventos import log_evento


def trabajo_cpu(peso, semilla):
    """Trabajo CPU-intensivo determinista: SHA-256 sobre `peso` bloques."""
    h = hashlib.sha256()
    for i in range(peso):
        h.update(str(semilla + i).encode())
    return h.hexdigest()


def cargador_cpu_main(cola_tareas, cola_resultados, intensidad, idx):
    for tarea in iter(cola_tareas.get, None):
        resumen = trabajo_cpu(intensidad, tarea)
        cola_resultados.put({"id": tarea, "checksum": resumen, "cargador": idx})


def procesamiento_main(cola_tareas, cola_resultados, n_cargadores, intensidad, estado, intervalo=1.0):
    detener = th.Event()

    def control():
        while not detener.is_set():
            detener.wait(intervalo)
            log_evento(estado, "procesamiento", "heartbeat control")

    th.Thread(target=control, daemon=True).start()
    procs = [
        mp.Process(target=cargador_cpu_main, args=(cola_tareas, cola_resultados, intensidad, i))
        for i in range(n_cargadores)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    detener.set()
    log_evento(estado, "procesamiento", f"{n_cargadores} cargadores finalizados")