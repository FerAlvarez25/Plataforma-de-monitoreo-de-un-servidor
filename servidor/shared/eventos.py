import time


def log_evento(estado, componente, mensaje):
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    estado.eventos.append(f"[{ts}] [{componente}] {mensaje}")


def leer_eventos(estado):
    return list(estado.eventos)


def contar_eventos(estado):
    return len(estado.eventos)