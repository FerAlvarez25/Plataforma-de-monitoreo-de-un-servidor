import subprocess
import sys


def test_smoke_servidor_modo_fix():
    cmd = [
        sys.executable, "-m", "servidor.main",
        "--total", "20", "--intensidad", "5",
        "--cargadores", "2", "--hilos-escritores", "2",
        "--capacidad", "8", "--tiempo-max", "20",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    assert res.returncode == 0, res.stderr
    assert "RESUMEN registrados=20 esperados=20 sync=mutex" in res.stdout


def test_smoke_servidor_registra_pids_cargadores():
    cmd = [
        sys.executable, "-m", "servidor.main",
        "--total", "10", "--intensidad", "3",
        "--cargadores", "2", "--hilos-escritores", "2",
        "--capacidad", "8", "--tiempo-max", "20",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    assert res.returncode == 0, res.stderr
    pids = [
        line for line in res.stdout.splitlines()
        if "cargador_cpu" in line and "pid=" in line
    ]
    assert len(pids) == 2, "deben registrarse los PIDs de los cargador_cpu"
    assert "pid=" in pids[0]