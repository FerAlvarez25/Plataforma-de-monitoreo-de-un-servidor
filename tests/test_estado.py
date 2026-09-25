from servidor.shared.estado import crear_estado


def test_estado_inicial():
    e = crear_estado()
    assert e.contador.value == 0
    assert len(e.registro) == 0
    assert len(e.metricas) == 0
    assert len(e.eventos) == 0
    assert hasattr(e, "lock_registro") and hasattr(e, "lock_metricas")


def test_locks_adquiribles():
    e = crear_estado()
    e.lock_registro.acquire()
    e.lock_registro.release()
    e.lock_metricas.acquire()
    e.lock_metricas.release()