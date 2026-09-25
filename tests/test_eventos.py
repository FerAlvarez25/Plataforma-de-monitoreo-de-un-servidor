import re

from servidor.shared.estado import crear_estado
from servidor.shared.eventos import contar_eventos, leer_eventos, log_evento


def test_log_formato_y_orden():
    e = crear_estado()
    log_evento(e, "admin", "inicio")
    log_evento(e, "monitoreo", "cpu=50%")
    eventos = leer_eventos(e)
    assert contar_eventos(e) == 2
    assert re.match(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[admin\] inicio$", eventos[0])
    assert "[monitoreo] cpu=50%" in eventos[1]