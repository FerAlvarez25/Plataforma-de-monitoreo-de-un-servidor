import time


def _rmw(estado, id_tarea, tipo):
    n = estado.contador.value          # 1) leer
    time.sleep(0.0002)                 # 2) ventana de carrera
    estado.contador.value = n + 1      # 3) escribir
    estado.registro[id_tarea] = {"tipo": tipo, "estado": "ok"}


def registrar_tarea(estado, id_tarea, tipo, sync=True):
    if sync:
        with estado.lock_registro:     # exclusión mutua sobre la RMW
            _rmw(estado, id_tarea, tipo)
    else:
        _rmw(estado, id_tarea, tipo)   # SIN protección -> carrera


def conteo_registrado(estado):
    return estado.contador.value


def listar_registros(estado):
    return [{"id": k, **v} for k, v in estado.registro.items()]