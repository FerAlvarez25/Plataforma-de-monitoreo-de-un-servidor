from servidor.componentes.reportes import contar_tipos, generar_resumen
from servidor.shared.estado import crear_estado
from servidor.shared.registro import registrar_tarea


def test_resumen_refleja_registro():
    e = crear_estado()
    registrar_tarea(e, 1, "a", sync=True)
    registrar_tarea(e, 2, "b", sync=True)
    registrar_tarea(e, 3, "b", sync=True)
    res = generar_resumen(e)
    assert res["total"] == 3
    assert res["tipos"] == {"a": 1, "b": 2}


def test_contar_tipos():
    e = crear_estado()
    registrar_tarea(e, 1, "x", sync=True)
    registrar_tarea(e, 2, "x", sync=True)
    assert contar_tipos(e) == {"x": 2}