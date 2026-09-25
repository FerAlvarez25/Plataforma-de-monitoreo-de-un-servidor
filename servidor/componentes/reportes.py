import time

from ..shared.eventos import log_evento
from ..shared.registro import conteo_registrado, listar_registros


def contar_tipos(estado):
    tipos = {}
    for v in estado.registro.values():
        t = v.get("tipo", "desconocido")
        tipos[t] = tipos.get(t, 0) + 1
    return tipos


def generar_resumen(estado):
    """Orden uniforme registro->metricas (sin inversión en reportes)."""
    with estado.lock_registro:
        time.sleep(0.1)
        with estado.lock_metricas:
            return {"total": conteo_registrado(estado), "tipos": contar_tipos(estado)}


def reportes_main(estado, paro, intervalo=0.5):
    while not paro.is_set():
        generar_resumen(estado)
        paro.wait(intervalo)
    log_evento(estado, "reportes", "finalizado")