from servidor.componentes.administrativas import depurar_registro
from servidor.shared.estado import crear_estado
from servidor.shared.registro import registrar_tarea


def test_depurar_respeta_limite():
    e = crear_estado()
    for i in range(20):
        registrar_tarea(e, i, "a", sync=True)
    depurar_registro(e, limite=5, invertido=False)
    assert len(e.registro) == 5
    assert all(i not in e.registro for i in range(15))  # se eliminan los más antiguos