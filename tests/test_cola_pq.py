import threading
import time

from servidor.shared.cola_pq import ColaProductorConsumidor
from servidor.shared.estado import crear_estado


def test_orden_fifo_respetando_capacidad():
    e = crear_estado()
    c = ColaProductorConsumidor(4, e._manager)
    assert c.size() == 0
    for i in range(4):
        c.put(i)
    assert c.size() == 4
    for i in range(4):
        assert c.get() == i


def test_capacidad_bloquea_put():
    e = crear_estado()
    c = ColaProductorConsumidor(2, e._manager)
    c.put("a")
    c.put("b")
    insertado = {"ok": False}

    def productor():
        c.put("c")
        insertado["ok"] = True

    h = threading.Thread(target=productor)
    h.start()
    time.sleep(0.2)
    assert not insertado["ok"]        # bloqueado por capacidad llena
    assert c.get() == "a"             # libera un hueco
    h.join(timeout=2)
    assert insertado["ok"]            # ahora sí pudo insertar
    assert c.get() == "b"
    assert c.get() == "c"


def test_get_vacia_bloquea():
    e = crear_estado()
    c = ColaProductorConsumidor(3, e._manager)
    obtenido = {"ok": False}

    def consumidor():
        c.get()
        obtenido["ok"] = True

    h = threading.Thread(target=consumidor)
    h.start()
    time.sleep(0.2)
    assert not obtenido["ok"]         # bloqueado en cola vacía
    c.put("x")
    h.join(timeout=2)
    assert obtenido["ok"]