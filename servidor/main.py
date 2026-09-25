"""Proceso administrador: coordina los 5 componentes del servidor."""
import argparse
import multiprocessing as mp
import sys
import threading
import time

from .shared.cola_pq import ColaProductorConsumidor
from .shared.estado import crear_estado
from .shared.eventos import log_evento
from .componentes.administrativas import administrativas_main
from .componentes.almacenamiento import almacenamiento_main
from .componentes.monitoreo import monitoreo_main
from .componentes.procesamiento import procesamiento_main
from .componentes.reportes import reportes_main


def generador_tareas(cola, total, demora, n_cargadores):
    for i in range(total):
        cola.put(i)
        if demora:
            time.sleep(demora)
    for _ in range(n_cargadores):       # centinelas: detienen la cola PQ
        cola.put(None)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Plataforma de monitoreo de un servidor")
    p.add_argument("--total", type=int, default=200)
    p.add_argument("--intensidad", type=int, default=50)
    p.add_argument("--cargadores", type=int, default=3)
    p.add_argument("--hilos-escritores", type=int, default=3)
    p.add_argument("--capacidad", type=int, default=16)
    p.add_argument("--raza", action="store_true", help="DEMO_RAZA: RMW sin lock")
    p.add_argument("--interbloqueo", action="store_true", help="DEMO_INTERBLOQUEO: orden invertido")
    p.add_argument("--demora", type=float, default=0.0)
    p.add_argument("--limite-registros", type=int, default=5000)
    p.add_argument("--tiempo-max", type=float, default=60.0)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    estado = crear_estado()
    cola_tareas = ColaProductorConsumidor(args.capacidad, estado._manager)
    cola_resultados = mp.Queue()
    paro = mp.Event()

    log_evento(estado, "admin", f"inicio servidor pid={mp.current_process().pid}")

    gen = threading.Thread(
        target=generador_tareas, args=(cola_tareas, args.total, args.demora, args.cargadores), daemon=True
    )
    gen.start()

    nombres = ["procesamiento", "almacenamiento", "reportes", "monitoreo", "administrativas"]
    hijos = [
        mp.Process(target=procesamiento_main,
                   args=(cola_tareas, cola_resultados, args.cargadores, args.intensidad, estado, 1.0)),
        mp.Process(target=almacenamiento_main,
                   args=(estado, cola_resultados, args.hilos_escritores, not args.raza)),
        mp.Process(target=reportes_main, args=(estado, paro, 0.5)),
        mp.Process(target=monitoreo_main, args=(estado, paro, 1.0)),
        mp.Process(target=administrativas_main, args=(estado, args.limite_registros, args.interbloqueo, paro, 0.5)),
    ]
    for p, nombre in zip(hijos, nombres):
        p.start()
        log_evento(estado, "admin", f"componente {nombre} pid={p.pid} iniciado")

    # 1) procesamiento consume la cola PQ: cuando termina ya no habrá más
    #    resultados -> se envían centinelas para liberar a almacenamiento.
    p_proc, p_alm = hijos[0], hijos[1]
    p_proc.join(timeout=args.tiempo_max)
    log_evento(estado, "admin",
               f"procesamiento pid={p_proc.pid} expirado" if p_proc.is_alive()
               else f"procesamiento pid={p_proc.pid} finalizado")
    if not p_proc.is_alive():
        for _ in range(args.hilos_escritores):   # centinelas: detienen almacenamiento
            cola_resultados.put(None)

    p_alm.join(timeout=args.tiempo_max)
    log_evento(estado, "admin",
               f"almacenamiento pid={p_alm.pid} expirado" if p_alm.is_alive()
               else f"almacenamiento pid={p_alm.pid} finalizado")

    # 2) Detiene los componentes de supervisión y reportes.
    paro.set()
    for p, nombre in zip(hijos[2:], nombres[2:]):
        p.join(timeout=5)
        log_evento(estado, "admin",
                   f"{nombre} pid={p.pid} expirado" if p.is_alive()
                   else f"{nombre} pid={p.pid} finalizado")

    # 3) Limpieza: no dejar procesos colgados en los modos demo.
    for p in hijos:
        if p.is_alive():
            p.terminate()
            p.join()

    sync = "raza" if args.raza else "mutex"
    log_evento(estado, "admin", f"RESUMEN registrados={estado.contador.value} esperados={args.total} sync={sync}")
    log_evento(estado, "admin", f"final servidor metricas={dict(estado.metricas)}")
    print("EVENTOS:")
    for ev in estado.eventos:
        print(ev)
    return 0


if __name__ == "__main__":
    sys.exit(main())