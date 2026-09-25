import glob
import os
import shutil
import subprocess
import sys

CARPETA_CARRERA = "tmp_evidencias_carrera"
CARPETA_INTERBLOQUEO = "tmp_evidencias_interbloqueo"


def _base_demo(modulo, carpeta):
    return [
        sys.executable, "-m", f"servidor.demos.{modulo}",
        "--total", "15", "--intensidad", "3",
        "--cargadores", "2", "--hilos-escritores", "2",
        "--capacidad", "8", "--tiempo-max", "5",
        "--carpeta", carpeta,
    ]


def _assert_artefactos(carpeta):
    for prefijo in ("01", "02", "04", "05", "06", "08"):
        assert glob.glob(f"{carpeta}/{prefijo}_*"), f"falta artefacto {prefijo}"


def test_carrera_exporta_artefactos():
    shutil.rmtree(CARPETA_CARRERA, ignore_errors=True)
    res = subprocess.run(_base_demo("escenario_carrera", CARPETA_CARRERA),
                         capture_output=True, text=True, timeout=90)
    assert res.returncode == 0, res.stderr + res.stdout
    _assert_artefactos(CARPETA_CARRERA)
    shutil.rmtree(CARPETA_CARRERA)


def test_interbloqueo_exporta_artefactos():
    shutil.rmtree(CARPETA_INTERBLOQUEO, ignore_errors=True)
    res = subprocess.run(_base_demo("escenario_interbloqueo", CARPETA_INTERBLOQUEO),
                         capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr + res.stdout
    _assert_artefactos(CARPETA_INTERBLOQUEO)
    shutil.rmtree(CARPETA_INTERBLOQUEO)