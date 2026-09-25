import time

from ..shared.eventos import log_evento

RUTINA_CORTA = 0.02  # trabajo simulado bajo el primer lock (segundos)


def depurar_registro(estado, limite, invertido):
    if invertido:                       # BUGGY: metricas -> registro (espera circular)
        with estado.lock_metricas:
            time.sleep(0.1)             # amplía la ventana contra reportes
            with estado.lock_registro:
                _podar(estado, limite)
    else:                               # FIX: registro -> metricas (orden uniforme)
        with estado.lock_registro:
            time.sleep(RUTINA_CORTA)
            with estado.lock_metricas:
                _podar(estado, limite)


def _podar(estado, limite):
    ids = list(estado.registro.keys())
    for k in ids[: max(0, len(ids) - limite)]:
        del estado.registro[k]


def administrativas_main(estado, limite, invertido, paro, intervalo=0.5):
    while not paro.is_set():
        depurar_registro(estado, limite, invertido)
        paro.wait(intervalo)
    log_evento(estado, "administrativas", "finalizado")