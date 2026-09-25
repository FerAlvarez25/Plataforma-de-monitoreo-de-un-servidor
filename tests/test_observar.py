import os


def test_script_existe_y_es_bash():
    ruta = os.path.join("herramientas", "observar.sh")
    assert os.path.exists(ruta)
    with open(ruta, encoding="utf-8") as f:
        primera = f.readline().strip()
    assert primera.startswith("#!/usr/bin/env bash")