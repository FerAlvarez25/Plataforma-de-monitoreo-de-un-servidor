import glob
import os
import shutil
import subprocess
import sys

CARPETA_CPU = "tmp_evidencias_cpu"


def _base_cpu_demo(carpeta):
    return [
        sys.executable, "-m", "servidor.demos.escenario_cpu_memoria",
        "--total-alta", "40", "--intensidad-alta", "8",
        "--total-baja", "20", "--intensidad-baja", "2",
        "--cargadores-alta", "2", "--cargadores-baja", "1",
        "--hilos-escritores", "2", "--capacidad", "8",
        "--tiempo-max", "10", "--carpeta", carpeta,
    ]


def test_cpu_memoria_exporta_artefactos():
    shutil.rmtree(CARPETA_CPU, ignore_errors=True)
    res = subprocess.run(_base_cpu_demo(CARPETA_CPU), capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr + res.stdout
    for prefijo in ("01", "02", "04", "05", "06", "08"):
        assert glob.glob(f"{CARPETA_CPU}/{prefijo}_*"), f"falta artefacto {prefijo}"
    shutil.rmtree(CARPETA_CPU)


def test_sesion_evidencias_existe_y_es_bash():
    ruta = os.path.join("herramientas", "sesion_evidencias.sh")
    assert os.path.exists(ruta)
    with open(ruta, encoding="utf-8") as f:
        assert f.readline().strip().startswith("#!/usr/bin/env bash")